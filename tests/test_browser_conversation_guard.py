"""Conversation browser snapshots must correlate replies, without Playwright."""
import ast
from pathlib import Path


def matcher():
    source=Path(__file__).parents[1]/'scripts/browser_e2e.py'
    tree=ast.parse(source.read_text())
    method=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='matching_conversation_reply')
    namespace={}
    exec(compile(ast.Module(body=[method],type_ignores=[]),str(source),'exec'),namespace)
    return namespace['matching_conversation_reply']


def test_new_transcript_does_not_accept_old_unrelated_response():
    match=matcher();expected={"I'll nod for you.",'Simulator heard: Please nod'}
    assert not match({'transcript':'Please nod','response':'Plants need water to survive.'},'Please nod',expected,'Plants need water to survive.')
    assert not match({'transcript':'Please nod','response':'A newly unrelated response'},'Please nod',expected,'Plants need water to survive.')
    assert match({'transcript':'Please nod','response':"I'll nod for you."},'Please nod',expected,'Plants need water to survive.')


def test_previous_identical_reply_cannot_count_as_new_turn():
    match=matcher();expected={"I'll nod for you."}
    assert not match({'transcript':'Please nod','response':"I'll nod for you."},'Please nod',expected,"I'll nod for you.")
    assert not match({'transcript':'Old transcript','response':"I'll nod for you."},'Please nod',expected,'old reply')
