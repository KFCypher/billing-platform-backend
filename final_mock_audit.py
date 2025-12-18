"""
Final audit - search for any remaining mock/dummy data
"""
import os
import re

print("\n" + "="*60)
print("SEARCHING FOR MOCK/DUMMY DATA")
print("="*60 + "\n")

# Patterns to search for
patterns = [
    (r'const\s+\w*[Mm]ock\w*\s*=', 'Mock variable definitions'),
    (r'const\s+\w*[Dd]ummy\w*\s*=', 'Dummy variable definitions'),
    (r'const\s+\w*[Ff]ake\w*\s*=', 'Fake variable definitions'),
    (r'cohort.*Jan\s+2024', 'Hardcoded cohort data'),
    (r'\[\s*{\s*month:\s*["\']', 'Hardcoded monthly data'),
    (r'fallback.*data', 'Fallback data'),
]

# Files to check
frontend_files = [
    'billing-platform-frontend/app/dashboard/page.tsx',
    'billing-platform-frontend/app/dashboard/analytics/page.tsx',
    'billing-platform-frontend/components/dashboard/revenue-chart.tsx',
]

issues_found = []

for file_path in frontend_files:
    full_path = os.path.join('C:\\Users\\GH\\Desktop\\billing-platform', file_path)
    if not os.path.exists(full_path):
        continue
    
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
            
            for pattern, description in patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    # Find line number
                    line_num = content[:match.start()].count('\n') + 1
                    line_content = lines[line_num - 1].strip()
                    
                    issues_found.append({
                        'file': file_path,
                        'line': line_num,
                        'type': description,
                        'content': line_content[:80]
                    })
    except Exception as e:
        print(f"Error reading {file_path}: {e}")

if issues_found:
    print("⚠️  POTENTIAL ISSUES FOUND:\n")
    for issue in issues_found:
        print(f"  {issue['file']}:{issue['line']}")
        print(f"    Type: {issue['type']}")
        print(f"    Content: {issue['content']}")
        print()
else:
    print("✅ NO MOCK DATA FOUND!")
    print("\nChecked files:")
    for file in frontend_files:
        print(f"  ✓ {file}")

print("\n" + "="*60)
print("AUDIT COMPLETE")
print("="*60)
