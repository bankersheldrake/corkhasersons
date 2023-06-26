import argparse
import os
import re
import tempfile
from bs4 import BeautifulSoup, Comment
import sys

def check_file_exists(filepath):
    try:
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"The file {filepath} does not exist.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

def convert_class_to_className(soup):
    for tag in soup():
        if 'class' in tag.attrs:
            tag.attrs['className'] = tag.attrs['class']
            del tag.attrs['class']
    return soup

def convert_styles_to_react(soup):
    for tag in soup():
        if 'style' in tag.attrs:
            styles = tag['style'].split(';')
            style_dict = {}
            for style in styles:
                if ':' in style:
                    key, value = style.split(':')
                    # Convert to camelCase
                    key = ''.join([word.capitalize() for word in key.split('-')]).replace(' ', '')
                    key = key[0].lower() + key[1:]  # Ensuring the first letter is lowercase
                    style_dict[key] = value.strip()
            # Convert the style dictionary to a string representation
            tag['style'] = '{{ ' + ', '.join(f'{k}: "{v}"' for k, v in style_dict.items()) + ' }}'
    return soup
def convert_griddivs_to_materialize(soup):
    try:
        for div in soup.find_all('div'):
            if 'class' in div.attrs:
                classes = div['class']
                if 'row' in classes:
                    div.name = 'Grid'
                    div.attrs['container'] = None
                    classes.remove('row')
                elif 'col' in classes:
                    div.name = 'Item'
                    oNewGrid = soup.new_tag("Grid")
                    div.wrap(oNewGrid)                    
                    classes.remove('col')
                    # Check for 's', 'm', and 'l' size classes
                    size_classes = [c for c in classes if c.startswith(('s', 'm', 'l'))]
                    if size_classes:
                        for size_class in size_classes:
                            # Size class format: s9, m6, l4 etc.
                            size, number = size_class[0], size_class[1:]
                            
                            if size == 's':
                                oNewGrid.attrs['xs'] = f'{{{number}}}'
                            elif size == 'm':
                                oNewGrid.attrs['sm'] = f'{{{number}}}'
                            elif size == 'l':
                                oNewGrid.attrs['md'] = f'{{{number}}}'
                            
                            # Create the Grid component with size prop

                            # grid_tag.attrs[size] = f'{{{number}}}'
                            # div.wrap(grid_tag)

                            # Create the Item component
                            # item_tag = soup.new_tag('Item')

                            # Move existing content inside the Item component
                            # for child in div.contents:
                            #     if child != item_tag:
                            #         item_tag.append(child)

                            # Append the Item component inside the Grid component
                            # div.append(item_tag)
                            # div.wrap(soup.new_tag("Item"))

                            classes.remove(size_class)
                else:
                    continue
                div['class'] = ' '.join(classes) if classes else None
                if not div['class']:
                    del div['class']
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    return soup


def convert_icons_to_react(soup):
    for icon in soup.find_all('i'):
        if 'class' in icon.attrs and 'material-icons' in icon.attrs['class']:
            icon.name = 'Icon'
            del icon.attrs['class']
    return soup

def add_rel_attribute(soup):
    for a in soup.find_all('a', href=True):
        if a['href'].startswith(('http', '#')) or a.get('target') == '_blank':
            a['rel'] = 'noopener noreferrer'
    return soup

def convert_buttons_to_react(soup):
    for anchor in soup.find_all('a'):
        # If anchor only contains an image, convert to IconButton
        if len(anchor.contents) == 1 and anchor.contents[0].name == 'img':
            anchor.name = 'IconButton'
        else:
            anchor.name = 'Button'

        anchor.attrs['className'] = 'left'
        anchor.attrs['node'] = 'button'
        anchor.attrs['style'] = "background-color: transparent; box-shadow: none;"
        anchor.attrs['waves'] = 'light'
        icon = anchor.find('i')
        if icon:
            icon.unwrap()  # Remove the <i> tag but keep its contents

        if 'href' in anchor.attrs and (anchor['href'].startswith(('http', '#')) or anchor.get('target') == '_blank'):
            anchor['rel'] = 'noopener noreferrer'
    return soup


def convert_comments_to_react(soup):
    comments = soup.find_all(string=lambda text: isinstance(text, Comment))
    for comment in comments:
        comment.replace_with(f'{{/*{comment}*/}}')
    return soup
def regex_final_cleanup(result):
    # Use a regex to replace style='{{...}}' with style={{...}}
    result = re.sub(r"style='{{(.*?)}}'", r'style={{\1}}', result)
    # result = re.sub(r'style="({{.*?}})"', r'style=\1', result)

    # Use a regex to replace s='{...}', m='{...}', and l='{...}' with s={...}, m={...}, and l={...} respectively.
    result = re.sub(r"s=\"{(\d+)}\"", r's={\1}', result)
    result = re.sub(r"m=\"{(\d+)}\"", r'm={\1}', result)
    result = re.sub(r"l=\"{(\d+)}\"", r'l={\1}', result)
    return result

def modify_html(input_path):
    try:
        with open(input_path, 'r') as file:
            data = file.read()

        soup = BeautifulSoup(data, 'html.parser')
        soup = convert_griddivs_to_materialize(soup)
        soup = convert_buttons_to_react(soup)  # Convert Materialize icon elements
        soup = convert_icons_to_react(soup)  # Convert Materialize icon elements
        soup = convert_comments_to_react(soup)  # Convert HTML comments to React
        
        soup = convert_styles_to_react(soup)
        soup = convert_class_to_className(soup)

        # Convert the soup to a string
        result = soup.prettify()
        return regex_final_cleanup(result)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

def main():
    try:
        parser = argparse.ArgumentParser(description='Convert HTML to React.')
        parser.add_argument("-i",'--input', help='Path to the input HTML file.')
        parser.add_argument("-o",'--output', help='Name of the output file.')

        args = parser.parse_args()

        check_file_exists(args.input)
        content = modify_html(args.input)
        # print(temp_output_file)
        # # Read the temp file content
        # with open(temp_output_file, 'r') as file:
        #     content = file.read()
        
        # # Remove the temp file
        # os.remove(temp_output_file)
        
        # Write content to the final output file
        with open(args.output, 'w') as file:
            print(f"Writing to {args.output}")
            file.write(content)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    
if __name__ == "__main__":
    main()
