# ElementTree `__len__` Gotcha

`xml.etree.ElementTree.Element.__len__()` returns the number of **child elements**, not the text length. For text-only elements like `<title>text</title>`, `len(element)` is `0` and `bool(element)` is `False`.

## The Bug

```python
# BROKEN — or fallback always evaluates the second branch
title_el = item.find("title") or item.find("atom:title", ns)
```

Since `bool(element)` is `False` for elements with zero children (text-only RSS/XML leaves), `or` always evaluates the fallback. This was discovered in `market_news.py` where `item.find("title") or item.find("atom:title", ns)` silently routed every RSS `<title>` to the Atom fallback (which returned `None`), producing 0 headlines from a perfectly valid RSS feed.

## The Fix

```python
# CORRECT — explicit None check
title_el = item.find("title")
if title_el is None:
    title_el = item.find("atom:title", ns)
```

Apply this to ANY `element.find(...) or element.find(...)` pattern targeting text-only elements.

## Detection Pattern

If XML parsing returns fewer results than expected and you've verified:
1. **Raw XML is valid** — `root.findall(".//item")` returns the right count
2. **Direct `find()` works** — `items[0].find("title")` returns a valid Element
3. **But the element is falsy** — `bool(element)` returns `False`

This is the `__len__` gotcha.

## Verification (run to confirm)

```python
import xml.etree.ElementTree as ET
root = ET.fromstring("<rss><item><title>Hello</title></item></rss>")
item = root.find(".//item")
title = item.find("title")

print(f"bool(title): {bool(title)}")       # False
print(f"len(title):  {len(title)}")        # 0
print(f"title.text:  {title.text}")        # "Hello"
print(f"is not None: {title is not None}") # True
```

## Root Cause

`Element.__len__` returns the count of child XML elements (matching the container protocol). Text content (`element.text`) is stored as a string attribute on the element, not as a child. This affects any text-only leaf element: `<title>`, `<link>`, `<description>`, `<pubDate>`, `<guid>`, and similar RSS/XML leaf nodes.
