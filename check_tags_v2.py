
import os

def count_tags(filepath):
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    tags = ['<div', '</div', '<TiltCard', '</TiltCard', '<motion.div', '</motion.div', '<>', '</>']
    results = {}
    for tag in tags:
        results[tag] = content.count(tag)
    
    for tag, count in results.items():
        print(f"{tag}: {count}")

count_tags(r'c:\Users\basav\OneDrive\Desktop\Credit_Decision_Analysis\credit-decision-engine\frontend\src\ModernDashboard.jsx')
