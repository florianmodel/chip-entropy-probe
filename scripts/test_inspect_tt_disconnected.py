"""Cheap negative tests for inspect-tt.py's disconnected-pin guard."""
import ast
from pathlib import Path

source = Path(__file__).with_name('inspect-tt.py').read_text()
tree = ast.parse(source)
guard = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'disconnected_pin_failures')
namespace = {}
exec(compile(ast.Module(body=[guard], type_ignores=[]), '<disconnected-pin-guard>', 'exec'), namespace)
check = namespace['disconnected_pin_failures']

expected = {f'uio_in[{j}]' for j in (0, 1, 2, 3, 7)}
assert check(5, expected) == {}
assert 'design__disconnected_pin__count' in check(6, expected)  # Hidden internal disconnect.
assert 'design__disconnected_pin__count' in check(4, expected)
assert 'reviewed_unused_inputs' in check(5, expected | {'uio_in[4]'})
assert 'design__disconnected_pin__count' in check(None, expected)
print('disconnected-pin guard negative tests passed')
