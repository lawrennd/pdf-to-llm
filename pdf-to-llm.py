import PyPDF2
import os
import re
from pathlib import Path
import yaml
from typing import Dict, Union

def wrap_text(text, width=80):
    """Wrap text to specified width while preserving paragraphs."""
    paragraphs = text.split('\n')
    wrapped_paragraphs = []
    
    for paragraph in paragraphs:
        if len(paragraph.strip()) == 0:
            wrapped_paragraphs.append('')
            continue
            
        # Preserve page markers
        if paragraph.strip().startswith('[Page'):
            wrapped_paragraphs.append(paragraph)
            continue
            
        # Wrap long paragraphs
        current_line = []
        current_length = 0
        
        for word in paragraph.split():
            word_length = len(word) + 1  # +1 for space
            if current_length + word_length > width:
                wrapped_paragraphs.append(' '.join(current_line))
                current_line = [word]
                current_length = word_length
            else:
                current_line.append(word)
                current_length += word_length
                
        if current_line:
            wrapped_paragraphs.append(' '.join(current_line))
            
    return '\n'.join(wrapped_paragraphs)

def clean_text(text):
    """Clean and normalize text content."""
    # Remove extra whitespace and normalize line endings
    text = re.sub(r'\s+', ' ', text)
    # Remove special characters but keep basic punctuation
    text = re.sub(r'[^\w\s.,!?;:()-]', '', text)
    # Fix spacing around punctuation
    text = re.sub(r'\s+([.,!?;:])', r'\1', text)
    # Wrap text to 80 characters
    text = wrap_text(text.strip())
    return text

def extract_toc_content(text):
    """Extract section titles and page numbers from TOC text."""
    # Common patterns in TOCs
    toc_pattern = re.compile(r'^(.*?)[.…\s]+(\d+)$', re.MULTILINE)
    
    # Find all matches
    matches = toc_pattern.findall(text)
    
    # Convert to markdown table
    if matches:
        table = "| Section | Page |\n|---------|------|\n"
        for section, page in matches:
            # Clean the section title
            section = section.strip()
            # Escape any pipe characters in the section title
            section = section.replace('|', '\\|')
            table += f"| {section} | {page} |\n"
        return table
    return text

class PageNumbering:
    def __init__(self, start_page: int, is_roman: bool = False):
        self.start_page = start_page
        self.is_roman = is_roman
        self._current = start_page

    def get_page_string(self, offset: int = 0) -> str:
        page_num = self._current + offset
        if self.is_roman:
            return self._to_roman(page_num)
        return str(page_num)

    @staticmethod
    def _to_roman(num: int) -> str:
        roman_symbols = [
            ('M', 1000), ('CM', 900), ('D', 500), ('CD', 400),
            ('C', 100), ('XC', 90), ('L', 50), ('XL', 40),
            ('X', 10), ('IX', 9), ('V', 5), ('IV', 4), ('I', 1)
        ]
        result = ''
        for symbol, value in roman_symbols:
            while num >= value:
                result += symbol
                num -= value
        return result.lower()  # Convert to lowercase for conventional thesis numbering

def load_section_config(config_path: str) -> Dict[str, PageNumbering]:
    """Load section configurations from YAML file."""
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    section_configs = {}
    for section, details in config.items():
        start_page = details.get('start_page', 1)
        is_roman = details.get('roman', False)
        section_configs[section] = PageNumbering(start_page, is_roman)
    
    return section_configs

def pdf_to_txt(pdf_path, output_dir, section_configs: Dict[str, PageNumbering]):
    """Convert a PDF file to cleaned text format with proper page numbering."""
    # Create output directory if it doesn't exist
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Get base filename without extension
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    
    # Get the appropriate page numbering configuration
    page_numbering = section_configs.get(base_name.lower(), 
                                       PageNumbering(1, False))  # Default to arabic starting at 1
    
    try:
        # Open PDF file
        with open(pdf_path, 'rb') as file:
            # Create PDF reader object
            pdf_reader = PyPDF2.PdfReader(file)
            
            # Extract and clean text
            full_text = []
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text = page.extract_text()
                cleaned_text = clean_text(text)
                
                if base_name.lower() == 'toc':
                    full_text.append(cleaned_text)
                else:
                    # Use the configured page numbering
                    page_string = page_numbering.get_page_string(page_num)
                    page_marker = f"\n[Page {page_string}]\n"
                    full_text.append(page_marker + cleaned_text)
            
            # Combine all pages (no need for additional spacing since we have page markers)
            final_text = '\n'.join(full_text)
            
            # Write to output file
            output_path = os.path.join(output_dir, f"{base_name}.txt")
            with open(output_path, 'w', encoding='utf-8') as out_file:
                out_file.write(final_text)
            
            return output_path
            
    except Exception as e:
        print(f"Error processing {pdf_path}: {str(e)}")
        return None

def process_directory(input_dir, output_dir, config_path):
    """Process all PDF files in a directory using the specified configuration."""
    # Load section configurations
    section_configs = load_section_config(config_path)
    
    pdf_files = [f for f in os.listdir(input_dir) if f.lower().endswith('.pdf')]
    
    for pdf_file in pdf_files:
        pdf_path = os.path.join(input_dir, pdf_file)
        output_path = pdf_to_txt(pdf_path, output_dir, section_configs)
        if output_path:
            print(f"Successfully converted {pdf_file} to {output_path}")
        else:
            print(f"Failed to convert {pdf_file}")

if __name__ == "__main__":
    input_directory = "pdf_chapters"
    output_directory = "txt_output"
    config_file = "thesis_config.yaml"
    
    process_directory(input_directory, output_directory, config_file)
