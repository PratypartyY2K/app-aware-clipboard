import re
from typing import Optional, List, Dict, Any
from enum import Enum

class Board(Enum):
    LINKS = "links"
    CODE = "code"
    COMMANDS = "commands"
    NOTES = "notes"
    OTHER = "other"

class _Predicate:
    def __init__(self, spec: Dict[str, Any]):
        self.type = spec.get('type')
        self.value = spec.get('value')
        self.field = spec.get('field', 'content')
        pattern = spec.get('pattern') or spec.get('value')
        self._compiled = None
        if self.type in ('app_regex', 'content_regex') and pattern:
            try:
                self._compiled = re.compile(pattern, re.IGNORECASE)
            except Exception:
                self._compiled = None

    def matches(self, app: Optional[str], content: Optional[str]) -> bool:
        app = (app or '').strip()
        content = (content or '').strip()
        typ = self.type
        if typ == 'app_contains':
            return self.value.lower() in app.lower()
        if typ == 'content_contains':
            return self.value.lower() in content.lower()
        if typ == 'app_regex':
            return bool(self._compiled and self._compiled.search(app))
        if typ == 'content_regex':
            return bool(self._compiled and self._compiled.search(content))
        if typ == 'startswith':
            target = app if self.field == 'app' else content
            return target.startswith(self.value)
        if typ == 'always':
            return True
        return False

class _Rule:
    def __init__(self, spec: Dict[str, Any]):
        preds = spec.get('predicates')
        if preds is None:
            preds = [ {k:v for k,v in spec.items() if k in ('type','value','pattern','field')} ]
        self.predicates = [_Predicate(p) for p in preds if p]
        board_val = spec.get('board')
        if isinstance(board_val, str):
            try:
                self.board = Board[board_val.upper()]
            except Exception:
                self.board = next((b for b in Board if b.value == board_val), Board.OTHER)
        else:
            self.board = Board.OTHER

    def matches(self, app: Optional[str], content: Optional[str]) -> bool:
        if not self.predicates:
            return False
        return all(p.matches(app, content) for p in self.predicates)

class BoardRouter:
    _default_rules_spec = [
        { 'predicates': [
            {'type': 'app_contains', 'value': 'chrome'},
            {'type': 'content_regex', 'pattern': r'https?://'},
        ], 'board': 'LINKS'},
        { 'predicates': [
            {'type': 'app_contains', 'value': 'safari'},
            {'type': 'content_regex', 'pattern': r'https?://'},
        ], 'board': 'LINKS'},
        { 'predicates': [
            {'type': 'app_contains', 'value': 'firefox'},
            {'type': 'content_regex', 'pattern': r'https?://'},
        ], 'board': 'LINKS'},
        {'predicates': [
            {'type':'app_contains','value':'terminal'},
            {'type':'content_contains','value':'$'}
        ], 'board':'COMMANDS'},
        {'predicates': [
            {'type':'app_contains','value':'iterm'},
            {'type':'content_contains','value':'$'}
        ], 'board':'COMMANDS'},
        {'predicates': [
            {'type':'app_contains','value':'vscode'},
            {'type':'content_contains','value':'{'}
        ], 'board':'CODE'},
        {'predicates': [
            {'type':'app_contains','value':'visual studio code'},
            {'type':'content_contains','value':'{'}
        ], 'board':'CODE'},
        {'predicates':[{'type':'content_regex','pattern': r'https?://'}], 'board':'LINKS'},
        {'predicates':[{'type':'content_contains','value':'$'}], 'board':'COMMANDS'},
        {'predicates':[{'type':'content_contains','value':'{'}], 'board':'CODE'},
        {'predicates':[{'type':'always','value':True}], 'board':'NOTES'}
    ]

    def __init__(self, rules_spec: Optional[List[Dict[str, Any]]] = None):
        specs = rules_spec if rules_spec is not None else self._default_rules_spec
        self.set_rules(specs)

    def set_rules(self, rules_spec: List[Dict[str, Any]]):
        self._rules = [_Rule(s) for s in rules_spec]

    def route(self, app_name: Optional[str], content: Optional[str]) -> Board:
        for r in self._rules:
            try:
                if r.matches(app_name, content):
                    return r.board
            except Exception:
                continue
        return Board.OTHER

    def assign_board_to_item(self, item) -> None:
        item.board = self.route(getattr(item, 'source_app', None), getattr(item, 'content', None))

    def rules_as_spec(self) -> List[Dict[str, Any]]:
        out = []
        for r in self._rules:
            spec = { 'predicates': [], 'board': r.board.name }
            for p in r.predicates:
                ps = {'type': p.type, 'field': p.field}
                if p._compiled is not None:
                    ps['pattern'] = p._compiled.pattern
                else:
                    ps['value'] = p.value
                spec['predicates'].append(ps)
            out.append(spec)
        return out

