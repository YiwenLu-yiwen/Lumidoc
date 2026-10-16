"""Cheap routing and bounded prompt history; ambiguous questions retain retrieval."""
import re

_DOCUMENT = re.compile(r'文档|文件|资料|知识库|上传|附件|合同|报告|上述|上面|根据|document|file|upload|knowledge\s*base|attachment|contract|report|according\s+to|above', re.I)
_GREETING = re.compile(r'^(你好|您好|嗨|谢谢|再见|hello|hi|hey|thanks|thank you|bye)[!！。,.，\s😊]*$', re.I)
_WRITING = re.compile(r'写|文案|模[板版]|小红书|润色|翻译|改写|write|draft|template|rewrite|translate|brainstorm', re.I)


def should_retrieve(message: str, history: list[dict], mode: str = 'auto') -> bool:
    if mode == 'off':
        return False
    if mode == 'always':
        return True
    if _GREETING.fullmatch(message.strip()):
        return False
    if _DOCUMENT.search(message):
        return True
    if _WRITING.search(message):
        # References to previous material are not independent creative requests.
        return bool(re.search(r'它|这个|这些|that|this|it\b', message, re.I)
                    and any(_DOCUMENT.search(item.get('content', '')) for item in history[-2:]))
    return True


def bounded_history(messages: list[dict], max_chars: int = 6000, max_messages: int = 6) -> list[dict]:
    result = []
    remaining = max_chars
    for message in reversed(messages):
        if len(result) >= max_messages or remaining <= 0:
            break
        if message.get('role') not in ('user', 'assistant'):
            continue
        content = message.get('content', '')[:min(2000, remaining)]
        result.append({'role': message['role'], 'content': content})
        remaining -= len(content)
    return list(reversed(result))
