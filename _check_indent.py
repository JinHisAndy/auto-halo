with open("tests/test_root_causes.py", "rb") as f:
    content = f.read()
lines = content.split(b"\n")
for i in range(596, 636):
    line = lines[i]
    indent = len(line) - len(line.lstrip())
    decoded = line.decode(errors="replace")
    print(f"{i+1}: indent={indent} | {decoded[:120]}")