"""消息去重和会话汇总；旧记录保留为一个历史会话。"""
def session_id(message):
    return message.get('session_id') or (message.get('meta_data') or {}).get('session_id') or 'legacy'


def unique_messages(messages):
    result, seen = [], set()
    for message in messages:
        key = message.get('id') or (session_id(message), message.get('role'), message.get('content'), str(message.get('timestamp')))
        if key in seen:
            continue
        seen.add(key)
        result.append({**message, 'session_id': session_id(message)})
    return sorted(result, key=lambda m: str(m.get('timestamp') or ''))


def conversation_summaries(messages):
    groups = {}
    for message in unique_messages(messages):
        key = session_id(message)
        content = message.get('content') or ''
        group = groups.setdefault(key, {'id':key, 'title':'', 'lastMessage':'', 'timestamp':'', 'messageCount':0})
        if not group['title'] and message.get('role') == 'user':
            group['title'] = content[:60]
        group.update(lastMessage=content[:120], timestamp=message.get('timestamp') or '')
        group['messageCount'] += 1
    return sorted(groups.values(), key=lambda g: str(g['timestamp']), reverse=True)
