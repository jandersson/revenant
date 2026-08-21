"""Read the subset of Ruby's Marshal format that LNet replies use.

LNet answers ;who / ;stats / ;channels with <data> elements whose text
is base64 of Marshal.dump'd Ruby objects — arrays and hashes of
strings, mostly. This reads exactly that subset: nil, booleans,
integers, strings (raw and ivar-wrapped), symbols and symbol links,
arrays, hashes, and object links. Anything else raises MarshalError
with the offending tag, so a new payload shape fails loudly instead of
misparsing quietly.
"""


class MarshalError(ValueError):
    """The bytes are not the Marshal 4.8 subset this reader speaks."""


def loads(data: bytes):
    if data[:2] != b"\x04\x08":
        raise MarshalError(f"not Marshal 4.8 data (header {data[:2]!r})")
    return _Reader(data, 2).value()


class _Reader:
    def __init__(self, data, position):
        self.data = data
        self.position = position
        self.symbols = []
        self.objects = []

    def read(self, count):
        chunk = self.data[self.position : self.position + count]
        if len(chunk) < count:
            raise MarshalError("truncated Marshal data")
        self.position += count
        return chunk

    def long(self):
        """Ruby's packed integer: a signed length prefix or small value."""
        first = self.read(1)[0]
        if first == 0:
            return 0
        signed = first - 256 if first > 127 else first
        if 1 <= signed <= 4:
            return int.from_bytes(self.read(signed), "little")
        if -4 <= signed <= -1:
            count = -signed
            return int.from_bytes(self.read(count), "little") - (1 << (8 * count))
        return signed - 5 if signed > 0 else signed + 5

    def value(self):
        tag = self.read(1)
        if tag == b"0":
            return None
        if tag == b"T":
            return True
        if tag == b"F":
            return False
        if tag == b"i":
            return self.long()
        if tag == b'"':
            text = self.read(self.long()).decode("utf-8", "replace")
            self.objects.append(text)
            return text
        if tag == b"I":
            # An ivar-wrapped value (a UTF-8 string, normally): the value
            # itself, then ivar pairs we read and discard (:E => true).
            inner = self.value()
            for _ in range(self.long()):
                self.value()
                self.value()
            return inner
        if tag == b":":
            name = self.read(self.long()).decode("utf-8", "replace")
            self.symbols.append(name)
            return name
        if tag == b";":
            return self.symbols[self.long()]
        if tag == b"[":
            items = []
            self.objects.append(items)
            for _ in range(self.long()):
                items.append(self.value())
            return items
        if tag == b"{":
            result = {}
            self.objects.append(result)
            for _ in range(self.long()):
                key = self.value()
                result[key] = self.value()
            return result
        if tag == b"@":
            return self.objects[self.long()]
        raise MarshalError(
            f"unsupported Marshal tag {tag!r} at byte {self.position - 1}"
        )
