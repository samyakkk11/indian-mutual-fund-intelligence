from pathlib import Path
root = Path(r"A:\Power BI projects\indian-mutual-fund-intelligence")
for f in sorted(root.rglob("*.py")):
    print(f.relative_to(root))