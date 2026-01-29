import os
import glob
from pypdf import PdfReader
import re

def extract_text_from_pdf(pdf_path, max_pages=None):
    try:
        reader = PdfReader(pdf_path)
        text = ""
        num_pages = len(reader.pages)
        
        # Read all pages, but we will filter relevant parts later
        # If the file is huge, this might be slow, but pypdf is usually okay.
        # Let's limit to first 5, last 5, and any page with keywords.
        
        relevant_pages = set()
        
        # First 3 pages (Abstract, Intro)
        for i in range(min(3, num_pages)):
            relevant_pages.add(i)
            
        # Last 3 pages (Conclusion, References - usually conclusion is before refs)
        for i in range(max(0, num_pages-3), num_pages):
            relevant_pages.add(i)
            
        # Scan for keywords
        keywords = ["best practice", "recommendation", "design pattern", "architecture", 
                    "lesson learned", "challenge", "future work", "conclusion", "mas system", "multi-agent"]
        
        # We need to scan all pages to find keywords, but full extraction might be heavy.
        # Let's just extract text from relevant pages found so far + a quick scan?
        # A full scan is safer to find specific content.
        
        full_text_map = {}
        
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                full_text_map[i] = page_text
                lower_text = page_text.lower()
                if any(k in lower_text for k in keywords):
                    relevant_pages.add(i)
        
        sorted_pages = sorted(list(relevant_pages))
        
        extracted_content = []
        for i in sorted_pages:
            if i in full_text_map:
                extracted_content.append(f"--- Page {i+1} ---\n{full_text_map[i]}")
        
        return "\n".join(extracted_content)
        
    except Exception as e:
        return f"Error reading {pdf_path}: {str(e)}"

def main():
    base_dir = "PDFs/Sources"
    # Find all PDFs recursively
    pdf_files = glob.glob(os.path.join(base_dir, "**/*.pdf"), recursive=True)
    
    print(f"Found {len(pdf_files)} PDF files.")
    
    report = ""
    
    for pdf_file in pdf_files:
        print(f"Processing: {pdf_file}")
        filename = os.path.basename(pdf_file)
        content = extract_text_from_pdf(pdf_file)
        
        # Heuristic to limit output size:
        # Take the first 1000 chars and any "keyword rich" sections.
        # For this tool, I'll just output the summary of findings per file.
        
        report += f"\n\n================================================================================\n"
        report += f"FILE: {filename}\n"
        report += f"================================================================================\n"
        
        # Simple extraction of paragraphs containing keywords
        lines = content.split('\n')
        relevant_lines = []
        keywords = ["best practice", "recommendation", "design", "architecture", "agent", "coordination"]
        
        for line in lines:
            if len(line.strip()) < 20: continue # Skip noise
            if any(k in line.lower() for k in keywords):
                relevant_lines.append(line.strip())
        
        # Output specific sections if detected (Abstract, Conclusion)
        # This is a bit rough, but good enough for me to read.
        report += content[:2000] # First 2000 chars (likely Abstract/Intro)
        report += "\n...\n[...Middle content skipped...]\n...\n"
        
        # Add last 2000 chars (likely Conclusion)
        if len(content) > 4000:
            report += content[-2000:]
        
    
    # Write report to a file so I can read it with tools if it's too big for stdout
    with open("temp_pdf_analysis.txt", "w", encoding="utf-8") as f:
        f.write(report)
        
    print("Analysis complete. Written to temp_pdf_analysis.txt")

if __name__ == "__main__":
    main()
