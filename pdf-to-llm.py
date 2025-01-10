import PyPDF2
import os
import re
from pathlib import Path
import yaml
from typing import Dict, Union
import referia as rf
import pandas as pd

def generate_thesis_config(data, index: str) -> Dict:
    """Generate thesis configuration from Referia data."""
    config = {}
    
    # Map of section names to their Referia column prefixes
    section_mappings = {
        'abstract': 'Abstract',
        'acknowledgments': 'Acknowledgments',
        'toc': 'ToC',
        'prologue': 'Prologue',
        'epilogue': 'Epilogue',
        'references': 'Ref',
        'appendix': 'App',
        'index': 'Index'
    }
    
    # Add chapter configurations
    for i in range(1, 13):  # Chapters 1-12
        chapter_key = f'chapter_{i}'
        prefix = f'Ch{i}'
        present = data.at[index, f'{prefix}Present']
        if pd.notna(present) and present:
            try:
                config[chapter_key] = {
                    'start_page': int(data.at[index, f'{prefix}FP']),
                    'end_page': int(data.at[index, f'{prefix}LP']),
                    'roman': False
                }
            except ValueError:
                raise ValueError(f"Invalid page numbers for Chapter {i} (Present={present}). "
                               f"Expected integers for start page ({data.at[index, f'{prefix}FP']}) "
                               f"and end page ({data.at[index, f'{prefix}LP']})")
    # Add other sections
    for config_key, prefix in section_mappings.items():
        present = data.at[index, f'{prefix}Present']
        if pd.notna(present) and present:
            config[config_key] = {
                'start_page': int(data.at[index, f'{prefix}FP']),
                'end_page': int(data.at[index, f'{prefix}LP']),
                'roman': config_key in ['abstract', 'acknowledgments', 'toc']  # Front matter uses roman numerals
            }
    return config

def split_pdf(pdf_path: str, output_dir: str, config: Dict):
    """Split PDF into sections based on configuration."""
    reader = PyPDF2.PdfReader(os.path.join(os.path.expanduser("~/Documents"), pdf_path))
    
    for section_name, section_config in config.items():
        writer = PyPDF2.PdfWriter()
        start_page = section_config['start_page'] - 1  # Convert to 0-based index
        end_page = section_config['end_page']
        
        for page_num in range(start_page, end_page):
            if page_num < len(reader.pages):
                writer.add_page(reader.pages[page_num])
        
        # Create output directory if it doesn't exist
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        output_path = os.path.join(output_dir, f"{section_name}.pdf")
        
        with open(output_path, 'wb') as output_file:
            writer.write(output_file)

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

def main():
    """Main function to process thesis using Referia data."""
    # Load Referia data
    interface = rf.config.interface.Interface.from_file(
        directory=".",
        user_file="_referia.yml"
    )
    data = rf.assess.data.CustomDataFrame.from_flow(interface)
    index = "Datta_Siddhartha"
    
    # Generate configuration
    config = generate_thesis_config(data, index)
    
    # Save configuration to YAML
    config_path = "thesis_config.yaml"
    with open(config_path, 'w') as f:
        yaml.dump(config, f)
    
    # Get thesis PDF path from Referia data
    pdf_path = data.at[index, 'ThesisPDF']
    
    # Create output directories
    pdf_output_dir = "pdf_chapters"
    txt_output_dir = "txt_output"
    
    # Split PDF into sections
    split_pdf(pdf_path, pdf_output_dir, config)
    
    # Process each section to text
    process_directory(pdf_output_dir, txt_output_dir, config_path)

if __name__ == "__main__":
    main()
