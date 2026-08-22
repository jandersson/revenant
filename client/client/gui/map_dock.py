"""The map dock: the community map drawn live around the character (#56).

MapView renders the BFS neighborhood of the current room — layout comes
from client/maplayout (Qt-free, where the tests live), Qt only draws.
It follows the engine's "room" stream as the character moves, and a
click on a room walks there (";go2 <id>" through the shared walker).
Survey rooms from the local overlay get a violet outline, the current
room is filled amber, compass edges draw straight and go/climb edges
dashed. The wheel zooms; dragging pans.
"""

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen
from PyQt6.QtWidgets import QGraphicsScene, QGraphicsView

from client.maplayout import ROOM_LIMIT, layout, resolve_room

CELL = 34  # grid pitch in pixels
ROOM = 14  # room square side
ZOOM_STEP = 1.15
ZOOM_RANGE = (0.3, 3.0)

CURRENT_FILL = QColor("#d8b465")  # amber, like the compass
ROOM_FILL = QColor("#23232b")
ROOM_EDGE = QColor("#8a8a96")
SURVEY_EDGE = QColor("#b39ddb")  # the local overlay, drawn distinctly
LINK_COLOR = QColor("#4a4a55")
TEXT_COLOR = QColor("#8a8a96")


class MapView(QGraphicsView):
    """The canvas; send is the frontend's command sink (GUI.write)."""

    def __init__(self, send):
        super().__init__(QGraphicsScene())
        self.send = send
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setBackgroundBrush(QBrush(QColor("#16161c")))
        self._db = None
        self._local_ids = set()
        self._room = None
        self._pending = None  # the last room frame, replayed once the db loads
        self._zoom = 1.0
        self._press_pos = None
        self._message("map database loading ...")

    # -- data feeds ------------------------------------------------------

    def set_database(self, db, local_ids):
        """The loader thread's delivery; None means no database on disk."""
        if db is None:
            self._message("no map database yet — ;go2 update downloads it")
            return
        self._db = db
        self._local_ids = local_ids
        if self._pending:
            self.update_room(*self._pending)
        else:
            self._message("waiting for a room ...")

    def update_room(self, uid, title):
        """Follow a "room" stream frame (uid + title per room change)."""
        self._pending = (uid, title)
        if self._db is None:
            return
        room = resolve_room(self._db, uid, title)
        if room is None:
            self._room = None
            self._message(f"off the map: {title or 'unknown room'}")
            return
        if room == self._room:
            return
        self._room = room
        self._render(room)

    # -- drawing ---------------------------------------------------------

    def _message(self, text):
        scene = self.scene()
        scene.clear()
        item = scene.addText(text)
        item.setDefaultTextColor(TEXT_COLOR)
        scene.setSceneRect(item.boundingRect())

    def _render(self, center):
        positions, edges = layout(self._db, center, limit=ROOM_LIMIT)
        scene = self.scene()
        scene.clear()
        straight = QPen(LINK_COLOR, 2)
        dashed = QPen(LINK_COLOR, 1, Qt.PenStyle.DashLine)
        for a, b, kind in edges:
            ax, ay = positions[a]
            bx, by = positions[b]
            scene.addLine(
                ax * CELL,
                ay * CELL,
                bx * CELL,
                by * CELL,
                straight if kind == "direction" else dashed,
            )
        for room_id, (x, y) in positions.items():
            rect = QRectF(x * CELL - ROOM / 2, y * CELL - ROOM / 2, ROOM, ROOM)
            outline = SURVEY_EDGE if room_id in self._local_ids else ROOM_EDGE
            fill = CURRENT_FILL if room_id == center else ROOM_FILL
            item = scene.addRect(rect, QPen(outline, 1.5), QBrush(fill))
            titles = self._db.rooms[room_id].get("title") or ["?"]
            item.setToolTip(f"{titles[0]} ({room_id})")
            item.setData(0, room_id)
        margin = CELL
        scene.setSceneRect(
            scene.itemsBoundingRect().adjusted(-margin, -margin, margin, margin)
        )
        self.centerOn(0, 0)

    # -- interaction -----------------------------------------------------

    def mousePressEvent(self, event):
        self._press_pos = event.position()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        # A click walks there; a drag (hand-scroll) must not. Qt's hand
        # drag consumes presses, so clicks are told apart by distance.
        moved = (
            self._press_pos is not None
            and (event.position() - self._press_pos).manhattanLength() > 4
        )
        self._press_pos = None
        super().mouseReleaseEvent(event)
        if moved:
            return
        for item in self.items(event.position().toPoint()):
            room_id = item.data(0)
            if room_id is not None:
                self.send(f";go2 {room_id}")
                return

    def wheelEvent(self, event):
        factor = ZOOM_STEP if event.angleDelta().y() > 0 else 1 / ZOOM_STEP
        low, high = ZOOM_RANGE
        factor = max(low / self._zoom, min(high / self._zoom, factor))
        self._zoom *= factor
        self.scale(factor, factor)
