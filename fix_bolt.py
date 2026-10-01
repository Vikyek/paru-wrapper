with open(".jules/bolt.md", "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if line.startswith("## 2024-10-25"):
        pass # Remove this line
    elif line.startswith("**Learning:** Using an O(N*M)"):
        pass # Remove this line
    elif line.startswith("**Action:** When filtering or matching"):
        pass # Remove this line
    else:
        new_lines.append(line)

with open(".jules/bolt.md", "w") as f:
    f.writelines(new_lines)
