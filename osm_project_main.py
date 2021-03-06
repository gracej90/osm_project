import xml.etree.cElementTree as ET

from collections import defaultdict
import pprint
import re

import csv
import codecs
import cerberus
import schema

osmfile = "portland_oregon.osm"
#osmfile = "sample.osm"

NODES_PATH = "nodes.csv"
NODE_TAGS_PATH = "nodes_tags.csv"
WAYS_PATH = "ways.csv"
WAY_NODES_PATH = "ways_nodes.csv"
WAY_TAGS_PATH = "ways_tags.csv"

# Compile a regular expression pattern into a regular expression object,
# which can be used for matching using its match() and search() methods"
LOWER_COLON = re.compile(r'^([a-z]|_)+:([a-z]|_)+')
PROBLEMCHARS = re.compile(r'[=\+/&<>;\'"\?%#$@\,\. \t\r\n]')
street_type_re = re.compile(r'\b\S+\.?$', re.IGNORECASE)

SCHEMA = schema.schema

# Make sure the fields order in the csvs matches the column order in the sql table schema
NODE_FIELDS = ['id', 'lat', 'lon', 'user', 'uid', 'version', 'changeset', 'timestamp']
NODE_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_FIELDS = ['id', 'user', 'uid', 'version', 'changeset', 'timestamp']
WAY_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_NODES_FIELDS = ['id', 'node_id', 'position']




def get_element(osm_file, tags=('node', 'way', 'relation')):
    """Yield element if it is the right type of tag

    Reference:
    http://stackoverflow.com/questions/3095434/inserting-newlines-in-xml-file-generated-via-xml-etree-elementtree-in-python
    """
    context = ET.iterparse(osm_file, events=('start', 'end'))
    _, root = next(context)
    for event, elem in context:
        if event == 'end' and elem.tag in tags:
            yield elem
            root.clear()

expected = ["Street", "Avenue", "Boulevard", "Drive", "Broadway", "Court", "Place", "Square", "Lane", "Road",
            "Trail", "Parkway", "Commons", "Circle", "Circus", "Highway", "Loop", "Terrace", "Way",
            "East", "West", "South", "North", "Alley", "Crest", "Run", "View"]


mapping = { "Ave": "Avenue",
            "Ave.": "Avenue",
            "Blvd": "Boulevard",
            "Blvd.": "Boulevard",
            "Cir": "Circle",
            "Dr": "Drive",
            "Dr.": "Drive",
            "Hwy": "Highway",
            "Rd": "Road",
            "Rd.": "Road",
            "Pkwy": "Parkway",
            "St": "Street",
            "St.": "Street",
            "street": "Street",
            "st.": "Street",
            "Ln": "Lane",
            }


# For auditing street_types
def is_street_name(elem):
    """Check to see if key is equal to addr:street and return bool value (true for succes, false otherwise)."""
    return (elem.attrib['k'] == "addr:street")


def audit_street_type(street_types, street_name):
    """
    Search the string 'street_name' for its street type and if not in 'expected' array, build and return 'street_types' dictionary.

    Args:
        street_types (str): first parameter
        street_name (str): second parameter

    Returns:
        dictionary of sets: [('street_type_A', set([street_name1, street_name2])), ('street_type_B', set([street_name1, street_name2]))]

    """
    m = street_type_re.search(street_name)
    if m:
        street_type = m.group()
        if street_type not in expected:
            street_types[street_type].add(street_name)
            return street_types

# For auditing postcodes
def is_postcode(elem):
    """Check to see if key is equal to addr:street and return bool value (true for succes, false otherwise)."""
    return (elem.attrib['k'] == "addr:postcode")

def audit_postcode(postcodes, postcode):
    """
    Build and return postcodes dictionary by adding postcode value sets.

    Args:
        postcodes (int): first parameter
        postcode (int): second parameter

    Returns:
        dictionary of sets

    """
    postcodes[postcode].add(postcode)
    return postcodes


# Main function running the audits
def audit(osmfile):
    """Open and iterate over osmfile, yield element if right tag, run audits on values of "tag" tags, pprint dictionaries as necessary."""
    osm_file = open(osmfile, "r")
    #keep track of unusual street_types
    street_types = defaultdict(set)
    postcodes = defaultdict(set)
    for i, elem in enumerate(get_element(osmfile)):
        if elem.tag == "node" or elem.tag == "way":
            #modifies behavior of .iter and only return "tag" tags
            for tag in elem.iter("tag"):
                if is_street_name(tag):
                    audit_street_type(street_types, tag.attrib['v'])
                elif is_postcode(tag):
                    audit_postcode(postcodes, tag.attrib['v'])
    osm_file.close()
    #pprint.pprint(dict(postcodes))
    #pprint.pprint(dict(street_types))


def update_name(name, mapping):
    """
    Search the string 'name' using regex, if street_type in mapping dictionary, update and return name.

    Args:
        name (str): first parameter
        mapping (str): second parameter

    Returns:
        name (str): updated name
    """
    #initialize m and search through arg. 'name' using regex
    m = street_type_re.search(name)
    if m:
        street_type = m.group()
        #if street_type in mapping, then substituate the value
        if street_type in mapping.keys():
            name = re.sub(street_type, mapping[street_type], name)
    return name


def update_postcode(postcode):
    """
    Match postcode to regex, select and return clean postcodes.

    Args:
        postcode (int): single parameter

    Returns:
        clean_postcode(int): updated postcode
    """
    search = re.match(r'^\D*(\d{5}).*', postcode)
    # select group that is captured
    clean_postcode = search.group(1)
    return clean_postcode


def shape_element(element, node_attr_fields=NODE_FIELDS, way_attr_fields=WAY_FIELDS,
                  problem_chars=PROBLEMCHARS, default_tag_type='regular'):
    """Clean and shape node or way XML element to Python dict."""
    """The function should take as input an iterparse Element object and return a dictionary."""
    node_attribs = {} #dictionary {'id': 757860928, 'user': }
    tags = []  # an array of dictionaries [{'id': 757860928,'key': 'amenity'},  {'id': 757860928}
    way_attribs = {}
    way_nodes = []

    if element.tag == 'node':
        for node_attrib_key, node_attrib_value in element.items():
            # if the key is in the array list

            if node_attrib_key in node_attr_fields:
                #add the key value pair to the dictionary
                node_attribs[node_attrib_key] = node_attrib_value
                # or
                # node_attribs[node_attrib_key] = element.get(node_attrib_key)

    if element.tag == 'way':
        for way_attrib_key in element.keys():
            if way_attrib_key in way_attr_fields:
                way_attribs[way_attrib_key] = element.get(way_attrib_key)


        count = 0
        for way_node in element.iter("nd"):
            way_nodes_dict = {}

            #set id
            way_nodes_dict["id"] = element.attrib["id"]

            #node_id
            way_nodes_dict["node_id"] = way_node.attrib["ref"]
            way_nodes_dict["position"] = count
            count += 1

            way_nodes.append(way_nodes_dict)

    for tag in element.iter("tag"):

        tags_dict = {}
        #set the id
        tags_dict["id"] = element.attrib["id"]

        #creating the key
        tag_key = tag.attrib["k"]
        if PROBLEMCHARS.search(tag_key):
            continue
        if LOWER_COLON.search(tag_key):
            tags_dict["key"] = tag_key.split(":", 1)[1]
            tags_dict["type"] = tag_key.split(":", 1)[0]
        else :
            tags_dict["key"] = tag_key
            tags_dict["type"] = default_tag_type

        #create and update value of street_name
        tag_value = tag.attrib["v"]
        if 'postcode' in tag_key:
            tags_dict["value"] = update_postcode(tag_value)
        else:
            tags_dict["value"] = update_name(tag_value, mapping)

        tags.append(tags_dict)

    if element.tag == 'node':
        return {'node': node_attribs, 'node_tags': tags}

    elif element.tag == 'way':
        return {'way': way_attribs, 'way_nodes': way_nodes, 'way_tags': tags}

# ================================================== #
#               Helper Functions                     #
# ================================================== #
def validate_element(element, validator, schema=SCHEMA):

    if validator.validate(element, schema) is not True:
        field, errors = next(validator.errors.iteritems())
        message_string = "\nElement of type '{0}' has the following errors:\n{1}"
        error_strings = (
            "{0}: {1}".format(k, v if isinstance(v, str) else ", ".join(v))
            for k, v in errors.iteritems()
        )
        raise cerberus.ValidationError(
            message_string.format(field, "\n".join(error_strings))
        )


class UnicodeDictWriter(csv.DictWriter, object):

    def writerow(self, row):
        super(UnicodeDictWriter, self).writerow({
            k: (v.encode('utf-8') if isinstance(v, unicode) else v) for k, v in row.iteritems()
        })

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)


# ================================================== #
#               Main Function                        #
# ================================================== #
def process_map(file_in, validate):

    with codecs.open(NODES_PATH, 'w') as nodes_file, \
         codecs.open(NODE_TAGS_PATH, 'w') as nodes_tags_file, \
         codecs.open(WAYS_PATH, 'w') as ways_file, \
         codecs.open(WAY_NODES_PATH, 'w') as way_nodes_file, \
         codecs.open(WAY_TAGS_PATH, 'w') as way_tags_file:

        nodes_writer = UnicodeDictWriter(nodes_file, NODE_FIELDS)
        node_tags_writer = UnicodeDictWriter(nodes_tags_file, NODE_TAGS_FIELDS)
        ways_writer = UnicodeDictWriter(ways_file, WAY_FIELDS)
        way_nodes_writer = UnicodeDictWriter(way_nodes_file, WAY_NODES_FIELDS)
        way_tags_writer = UnicodeDictWriter(way_tags_file, WAY_TAGS_FIELDS)

        nodes_writer.writeheader()
        node_tags_writer.writeheader()
        ways_writer.writeheader()
        way_nodes_writer.writeheader()
        way_tags_writer.writeheader()

        validator = cerberus.Validator()

        for element in get_element(file_in, tags=('node', 'way')):
            el = shape_element(element)
            if el:
                if validate is True:
                    validate_element(el, validator)

                if element.tag == 'node':
                    nodes_writer.writerow(el['node'])
                    node_tags_writer.writerows(el['node_tags'])
                elif element.tag == 'way':
                    ways_writer.writerow(el['way'])
                    way_nodes_writer.writerows(el['way_nodes'])
                    way_tags_writer.writerows(el['way_tags'])


if __name__ == '__main__':
    # Note: Validation is ~ 10X slower. For the project consider using a small
    # sample of the map when validating.
    process_map(osmfile, validate=True)
