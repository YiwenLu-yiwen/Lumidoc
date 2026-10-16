from src.modules.chat.conversations import unique_messages, conversation_summaries

def test_multiple_turns_are_one_conversation_and_legacy_is_grouped():
    messages = [
        {'id':'1','role':'user','content':'first','session_id':'a','timestamp':'1'},
        {'id':'2','role':'assistant','content':'answer','session_id':'a','timestamp':'2'},
        {'id':'3','role':'user','content':'followup','session_id':'a','timestamp':'3'},
        {'id':'4','role':'user','content':'separate','session_id':'b','timestamp':'4'},
        {'id':'5','role':'user','content':'old','timestamp':'5'},
        {'id':'6','role':'assistant','content':'old answer','timestamp':'6'},
    ]
    result = conversation_summaries(messages)
    assert len(result)==3
    by_id={r['id']:r for r in result}
    assert by_id['a']['messageCount']==3
    assert by_id['a']['title']=='first'
    assert by_id['legacy']['messageCount']==2

def test_duplicate_copies_removed_but_intentional_repeated_questions_kept():
    first={'id':'1','role':'user','content':'again','timestamp':'1'}
    later={'id':'2','role':'user','content':'again','timestamp':'2'}
    assert [m['id'] for m in unique_messages([first,dict(first),later])]==['1','2']
