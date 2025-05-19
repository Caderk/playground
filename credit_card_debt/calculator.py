import re

# The raw input string
data = """
USD 2,14 	
USD 23,80 	
	USD 34,73
	USD 66,15 
"""

# Prepare lists for left and right column values
left = []  # Avances y Compras, Cuotas 
right = []

for line in data.splitlines():
    if not line.strip():
        continue
    
    # Determine if it's right column by leading tab or spaces
    is_right = bool(line.startswith('\t'))
    
    # Remove currency prefixes and extract the number
    line_clean = re.sub(r'(USD|\$)', '', line)
    match = re.search(r'[\d\.,]+', line_clean)
    if not match:
        continue
    num_str = match.group(0)
    
    # Normalize number: remove thousand separators, unify decimal point
    num_str = num_str.replace('.', '').replace(',', '.').strip()
    
    # Convert to float
    value = float(num_str)
    
    # Append to appropriate list
    if is_right:
        right.append(value)
        print('-', num_str)
    else:
        left.append(value)
        print('+', num_str)


# Calculate totals
left_total = sum(left)
right_total = sum(right)
difference = left_total - right_total

# Display results
print(f"Left column total:  {left_total:.2f}")
print(f"Right column total: {right_total:.2f}")
print(f"Difference (Left - Right): {difference:.2f}")
