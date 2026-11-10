"""UTF-8 storage with a fallback for files written by older Windows builds."""
import locale
from pathlib import Path


def read_text_compat(path):
    path = Path(path)
    try:
        return path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        return path.read_text(encoding=locale.getencoding())


def write_text_utf8(path, content):
    return Path(path).write_text(content, encoding='utf-8')


def repair_legacy_mojibake(value):
    """Repair the characteristic UTF-8-as-GBK filenames from older Windows records."""
    if not isinstance(value, str) or not any(mark in value for mark in ('锛', '寮', '鎬', '揩', '級')):
        return value
    try:
        repaired = value.encode('gbk').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value
    before=sum(value.count(mark) for mark in ('锛', '寮', '鎬', '揩', '級'))
    after=sum(repaired.count(mark) for mark in ('锛', '寮', '鎬', '揩', '級'))
    return repaired if after < before else value
