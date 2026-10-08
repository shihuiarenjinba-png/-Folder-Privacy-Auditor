import ast
from pathlib import Path

source = Path(__file__).with_name("windows_app.py")
tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
checked = 0
for node in ast.walk(tree):
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        continue
    owner = node.func.value
    if not isinstance(owner, ast.Name) or owner.id != "filedialog":
        continue
    if not node.func.attr.startswith("ask"):
        continue
    checked += 1
    assert any(keyword.arg == "parent" for keyword in node.keywords), (
        f"filedialog.{node.func.attr} at line {node.lineno} must set parent=self.root"
    )
assert checked > 0, "No filedialog calls were checked"
print(f"Dialog parent smoke test: OK ({checked} calls)")
