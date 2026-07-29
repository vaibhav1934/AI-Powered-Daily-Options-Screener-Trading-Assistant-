import os, glob, re

for f in glob.glob('f*.py'):
    with open(f, 'r') as file:
        content = file.read()
    
    # Extract F number
    match = re.search(r'factor_id = "F(\d+)"', content)
    if match:
        num = int(match.group(1))
        if num >= 41 and num <= 45:
            content = re.sub(r'layer = \d+', 'layer = 9', content)
        elif num >= 46 and num <= 50:
            content = re.sub(r'layer = \d+', 'layer = 10', content)
            
        with open(f, 'w') as file:
            file.write(content)
