"""Small explicit class graph, not a complete OWL reasoner."""
from decimal import Decimal, InvalidOperation, localcontext


def money(value):
    try:
        d = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError('金额必须为有效十进制数') from exc
    if not d.is_finite() or d < 0 or len(d.as_tuple().digits) > 24 or abs(d.as_tuple().exponent) > 12:
        raise ValueError('金额必须为有限非负数，且精度在演示范围内')
    return d


def evaluate_limit(effective, used, amount, period):
    if period not in ('SINGLE', 'DAILY'):
        raise ValueError('不支持的限额周期')
    cap, requested = money(effective), money(amount)
    if period == 'SINGLE':
        return {'exceeded': requested > cap, 'remaining': None}
    if used is None:
        return {'exceeded': None, 'remaining': None}
    with localcontext() as ctx:
        ctx.prec = 50
        consumption = money(used)
        return {'exceeded': consumption + requested > cap, 'remaining': format(cap - consumption, 'f')}


class OntologyGraph:
    def __init__(self, data):
        self.data = data
        self.classes = data['classes']
        for name in self.classes:
            self.ancestors(name)

    def ancestors(self, name):
        found = []
        def visit(node, path):
            if node in path:
                raise ValueError('本体类层级存在环')
            if node not in self.classes:
                raise ValueError('未定义的本体类: ' + node)
            if node not in found:
                found.append(node)
            for parent in self.classes[node]['parents']:
                visit(parent, path + [node])
        visit(name, [])
        return found

    def is_a(self, name, parent):
        return parent in self.ancestors(name)

    def category(self, name):
        values = {self.classes[n]['reason_category'] for n in self.ancestors(name) if 'reason_category' in self.classes[n]}
        if len(values) != 1:
            raise ValueError('原因分类缺失或有歧义: ' + name)
        return next(iter(values))

    def actions(self, name):
        return [a for a in self.data['actions'] if self.is_a(name, a['applies_to'])]
