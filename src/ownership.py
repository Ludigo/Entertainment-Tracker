"""Display ownership without assigning formats to legacy records."""
def describe(record):
    formats=[]
    if record.get('owned_physical'):formats.append('Physical')
    if record.get('owned_digital'):formats.append('Digital')
    return ' + '.join(formats) if formats else 'Owned — format unspecified' if record.get('owned') else 'Not marked owned'
