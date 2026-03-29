
import os

def count_tags(filepath):
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    opens_div = content.count('<div')
    closes_div = content.count('</div')
    print(f"div: Opens={opens_div}, Closes={closes_div}")
    
    opens_tilt = content.count('<TiltCard')
    closes_tilt = content.count('</TiltCard')
    print(f"TiltCard: Opens={opens_tilt}, Closes={closes_tilt}")
    
    opens_motion = content.count('<motion.div')
    closes_motion = content.count('</motion.div')
    print(f"motion.div: Opens={opens_motion}, Closes={closes_motion}")
    
    opens_frag = content.count('<>') 
    closes_frag = content.count('</>')
    print(f"Fragments: Opens={opens_frag}, Closes={closes_frag}")

count_tags(r'c:\Users\basav\OneDrive\Desktop\Credit_Decision_Analysis\credit-decision-engine\frontend\src\ModernDashboard.jsx')
