# -*- coding: utf-8 -*-
"""
PubChemPy

Python interface for the PubChem PUG REST service.
https://github.com/mcs07/PubChemPy
"""

import json
import os
import time
import urllib
import urllib2


__author__ = 'Matt Swain'
__email__ = 'm.swain@me.com'
__version__ = '1.0'


API_BASE = 'https://pubchem.ncbi.nlm.nih.gov/rest/pug'


def request(identifier, namespace='cid', domain='compound', operation=None, output='JSON', searchtype=None, **kwargs):
    """
    Construct API request from parameters and return the response.

    Full specification at http://pubchem.ncbi.nlm.nih.gov/pug_rest/PUG_REST.html
    """

    # If identifier is a list, join with commas into string
    if isinstance(identifier, int):
        identifier = str(identifier)
    if not isinstance(identifier, basestring):
        identifier = ','.join(str(x) for x in identifier)

    # Filter None values from kwargs
    kwargs = dict((k,v) for k,v in kwargs.iteritems() if v is not None)

    # Build API URL
    urlid, postdata = None, None
    if namespace in ['listkey', 'formula'] or (searchtype and namespace == 'cid') or domain == 'sources':
        urlid = urllib2.quote(identifier.replace('/','.'))
    else:
        postdata = '%s=%s' % (namespace, urllib2.quote(identifier.replace('/','.')))
    comps = filter(None, [API_BASE, domain, searchtype, namespace, urlid, operation, output])
    apiurl = '/'.join(comps)
    if kwargs:
        apiurl+= '?%s' % urllib.urlencode(kwargs)

    # Make request
    try:
        print apiurl
        response = urllib2.urlopen(apiurl, postdata).read()
        return response
    except urllib2.HTTPError as e:
        raise PubChemHTTPError(e)

def get(identifier, namespace='cid', domain='compound', operation=None, output='JSON', searchtype=None, **kwargs):
    """ Request wrapper that automatically handles async requests. """
    if searchtype or namespace in ['formula']:
        response = request(identifier, namespace, domain, None, 'JSON', searchtype, **kwargs)
        status = json.loads(response)
        if 'Waiting' in status and 'ListKey' in status['Waiting']:
            identifier = status['Waiting']['ListKey']
            namespace = 'listkey'
            while 'Waiting' in status and 'ListKey' in status['Waiting']:
                time.sleep(2)
                response = request(identifier, namespace, domain, operation, 'JSON', **kwargs)
                status = json.loads(response)
            if not output == 'JSON':
                response = request(identifier, namespace, domain, operation, output, searchtype, **kwargs)
    else:
        response = request(identifier, namespace, domain, operation, output, searchtype, **kwargs)
    return response

def get_compounds(identifier, namespace='cid', searchtype=None, **kwargs):
    """ Retrieve the specified compound records from PubChem. """
    results = json.loads(get(identifier, namespace, searchtype=searchtype, **kwargs))
    compounds = [Compound(r) for r in results['PC_Compounds']]
    return compounds

def get_substances(identifier, namespace='sid', **kwargs):
    """ Retrieve the specified substance records from PubChem. """
    results = json.loads(get(identifier, namespace, 'substance', **kwargs))
    substances = [Substance(r) for r in results['PC_Substances']]
    return substances

def get_assays(identifier, namespace='aid', sids=None, **kwargs):
    """ Retrieve the specified assay records from PubChem. """
    results = json.loads(get(identifier, namespace, 'assay', sids, **kwargs))
    assays = [Assay(r) for r in results['PC_AssayContainer']]
    return assays

def get_properties(properties, identifier, namespace='cid', searchtype=None, **kwargs):
    if not isinstance(properties, basestring):
        properties = ','.join(properties)
    properties = 'property/%s' % properties
    results = json.loads(get(identifier, namespace, 'compound', properties, searchtype=searchtype, **kwargs))
    results = results['PropertyTable']['Properties']
    return results

def get_synonyms(identifier, namespace='cid', domain='compound', searchtype=None, **kwargs):
    results = json.loads(get(identifier, namespace, domain, 'synonyms', searchtype=searchtype, **kwargs))
    synonyms = results['InformationList']['Information']
    return synonyms

def get_cids(identifier, namespace='name', domain='compound', searchtype=None, **kwargs):
    results = json.loads(get(identifier, namespace, domain, 'cids', searchtype=searchtype, **kwargs))
    if 'IdentifierList' in results:
        results = results['IdentifierList']['CID']
    elif 'InformationList' in results:
        results = results['InformationList']['Information']
    return results

def get_sids(identifier, namespace='cid', domain='compound', searchtype=None, **kwargs):
    results = json.loads(get(identifier, namespace, domain, 'sids', searchtype=searchtype, **kwargs))
    print results
    if 'IdentifierList' in results:
        results = results['IdentifierList']['SID']
    elif 'InformationList' in results:
        results = results['InformationList']['Information']
    return results

def get_aids(identifier, namespace='cid', domain='compound', searchtype=None, **kwargs):
    results = json.loads(get(identifier, namespace, domain, 'aids', searchtype=searchtype, **kwargs))
    if 'IdentifierList' in results:
        results = results['IdentifierList']['AID']
    elif 'InformationList' in results:
        results = results['InformationList']['Information']
    return results

# TODO: Assay Description, Summary, Dose-response
# TODO: Classification, Dates, XRefs operations

def get_all_sources(domain='substance'):
    """ Return a list of all current depositors of substances or assays. """
    results = json.loads(get(domain, None, 'sources'))
    sources = results['InformationList']['SourceName']
    return sources

def download(format, path, identifier, namespace='cid', domain='compound', operation=None, searchtype=None, overwrite=False, **kwargs):
    """ Format can be  XML, ASNT/B, JSON, SDF, CSV, PNG, TXT.  """
    response = get(identifier, namespace, domain, operation, format, searchtype, **kwargs)
    if not overwrite and os.path.isfile(path):
        raise IOError("%s already exists. Use 'overwrite=True' to overwrite it." % filename)
    with open(path, 'w') as file:
        file.write(response)

class Compound(object):
    def __init__(self, record):
        self.record = record

    @classmethod
    def from_cid(cls, cid, **kwargs):
        record = json.loads(request(cid, **kwargs))['PC_Compounds'][0]
        return cls(record)

    def __repr__(self):
        return 'Compound(%s)' % self.cid if self.cid else 'Compound()'

    @property
    def cid(self):
        # Note: smiles or inchi inputs can return compounds without a cid
        if 'id' in self.record and 'id' in self.record['id'] and 'cid' in self.record['id']['id']:
            return self.record['id']['id']['cid']

    @property
    def elements(self):
        return self.record['atoms']['element']

    @property
    def atoms(self):
        a = {
            'x' : self.record['coords'][0]['conformers'][0]['x'],
            'y' : self.record['coords'][0]['conformers'][0]['y'],
            'element' : self.record['atoms']['element']
        }
        if 'z' in self.record['coords'][0]['conformers'][0]:
            a['z'] = self.record['coords'][0]['conformers'][0]['z']
        return map(dict, zip(*[[(k, v) for v in value] for k, value in a.items()]))

    @property
    def bonds(self):
        # TODO: Get self.record['coords'][0]['conformers'][0]['style']
        return map(dict, zip(*[[(k, v) for v in value] for k, value in self.record['bonds'].items()]))

    @property
    def coordinate_type(self):
        if 'twod' in self.record['coords']['type']:
            return '2d'
        elif 'threed' in self.record['coords']['type']:
            return '3d'

    @property
    def charge(self):
        if 'charge' in self.record:
            return self.record['charge']

    @property
    def molecular_formula(self):
        return parse_prop({'label':'Molecular Formula'}, self.record['props'])

    @property
    def molecular_weight(self):
        return parse_prop({'label':'Molecular Weight'}, self.record['props'])

    @property
    def canonical_smiles(self):
        return parse_prop({'label':'SMILES','name':'Canonical'}, self.record['props'])

    @property
    def isomeric_smiles(self):
        return parse_prop({'label':'SMILES','name':'Isomeric'}, self.record['props'])

    @property
    def inchi(self):
        return parse_prop({'label':'InChI','name':'Standard'}, self.record['props'])

    @property
    def inchikey(self):
        return parse_prop({'label':'InChIKey','name':'Standard'}, self.record['props'])

    @property
    def iupac_name(self):
        # Note: Allowed, CAS-like Style, Preferred, Systematic, Traditional are available in full record
        return parse_prop({'label':'IUPAC Name','name':'Preferred'}, self.record['props'])

    @property
    def xlogp(self):
        return parse_prop({'label':'Log P'}, self.record['props'])

    @property
    def exact_mass(self):
        return parse_prop({'label':'Mass','name':'Exact'}, self.record['props'])

    @property
    def monoisotopic_mass(self):
        return parse_prop({'label':'Weight','name':'MonoIsotopic'}, self.record['props'])

    @property
    def tpsa(self):
        return parse_prop({'implementation':'E_TPSA'}, self.record['props'])

    @property
    def complexity(self):
        return parse_prop({'implementation':'E_COMPLEXITY'}, self.record['props'])

    @property
    def h_bond_donor_count(self):
        return parse_prop({'implementation':'E_NHDONORS'}, self.record['props'])

    @property
    def h_bond_acceptor_count(self):
        return parse_prop({'implementation':'E_NHACCEPTORS'}, self.record['props'])

    @property
    def rotatable_bond_count(self):
        return parse_prop({'implementation':'E_NROTBONDS'}, self.record['props'])

    @property
    def fingerprint(self):
        return parse_prop({'implementation':'E_SCREEN'}, self.record['props'])

    @property
    def heavy_atom_count(self):
        if 'count' in self.record and 'heavy_atom' in self.record['count']:
            return self.record['count']['heavy_atom']

    @property
    def isotope_atom_count(self):
        if 'count' in self.record and 'isotope_atom' in self.record['count']:
            return self.record['count']['isotope_atom']

    @property
    def atom_stereo_count(self):
        if 'count' in self.record and 'atom_chiral' in self.record['count']:
            return self.record['count']['atom_chiral']

    @property
    def defined_atom_stereo_count(self):
        if 'count' in self.record and 'atom_chiral_def' in self.record['count']:
            return self.record['count']['atom_chiral_def']

    @property
    def undefined_atom_stereo_count(self):
        if 'count' in self.record and 'atom_chiral_undef' in self.record['count']:
            return self.record['count']['atom_chiral_undef']

    @property
    def bond_stereo_count(self):
        if 'count' in self.record and 'bond_chiral' in self.record['count']:
            return self.record['count']['bond_chiral']

    @property
    def defined_bond_stereo_count(self):
        if 'count' in self.record and 'bond_chiral_def' in self.record['count']:
            return self.record['count']['bond_chiral_def']

    @property
    def undefined_bond_stereo_count(self):
        if 'count' in self.record and 'bond_chiral_undef' in self.record['count']:
            return self.record['count']['bond_chiral_undef']

    @property
    def covalent_unit_count(self):
        if 'count' in self.record and 'covalent_unit' in self.record['count']:
            return self.record['count']['covalent_unit']

    @property
    def volume_3d(self):
        conf = self.record['coords'][0]['conformers'][0]
        if 'data' in conf:
            return parse_prop({'label':'Shape','name':'Volume'}, conf['data'])

    @property
    def multipoles_3d(self):
        conf = self.record['coords'][0]['conformers'][0]
        if 'data' in conf:
            return parse_prop({'label':'Shape','name':'Multipoles'}, conf['data'])

    @property
    def conformer_rmsd_3d(self):
        coords = self.record['coords'][0]
        if 'data' in coords:
            return parse_prop({'label':'Conformer','name':'RMSD'}, coords['data'])

    @property
    def effective_rotor_count_3d(self):
        return parse_prop({'label':'Count','name':'Effective Rotor'}, self.record['props'])

    @property
    def pharmacophore_features_3d(self):
        return parse_prop({'label':'Features','name':'Pharmacophore'}, self.record['props'])

    @property
    def mmff94_partial_charges_3d(self):
        return parse_prop({'label':'Charge','name':'MMFF94 Partial'}, self.record['props'])

    @property
    def mmff94_energy_3d(self):
        conf = self.record['coords'][0]['conformers'][0]
        if 'data' in conf:
            return parse_prop({'label':'Energy','name':'MMFF94 NoEstat'}, conf['data'])

    @property
    def conformer_id_3d(self):
        conf = self.record['coords'][0]['conformers'][0]
        if 'data' in conf:
            return parse_prop({'label':'Conformer','name':'ID'}, conf['data'])

    @property
    def shape_selfoverlap_3d(self):
        conf = self.record['coords'][0]['conformers'][0]
        if 'data' in conf:
            return parse_prop({'label':'Shape','name':'Self Overlap'}, conf['data'])

    @property
    def feature_selfoverlap_3d(self):
        conf = self.record['coords'][0]['conformers'][0]
        if 'data' in conf:
            return parse_prop({'label':'Feature','name':'Self Overlap'}, conf['data'])

    @property
    def shape_fingerprint_3d(self):
        conf = self.record['coords'][0]['conformers'][0]
        if 'data' in conf:
            return parse_prop({'label':'Fingerprint','name':'Shape'}, conf['data'])


def parse_prop(filter, proplist):
    """ Extract property value from record using the given urn filter.  """
    props = [i for i in proplist if all(item in i['urn'].items() for item in filter.items())]
    if len(props) > 0:
        return props[0]['value'][props[0]['value'].keys()[0]]



    # TODO: Parse record to extract cid, properties
    # property methods for different operations - record, properties, synonyms, sids, aids, assaysummary, classification
    # Parse properties from record where possible
    # Extra request for other properties + synonyms etc.
    # Many methods have options too - e.g. cids, aids, sids
    # method to print/save a certain format to file

class Substance(object):
    def __init__(self, record):
        self.record = record

    @classmethod
    def from_sid(cls, sid):
        record = json.loads(request(sid, 'sid', 'substance'))['PC_Substances'][0]
        return cls(record)

    @property
    def sid(self):
        return self.record['id']['id']['sid']

class Assay(object):
    def __init__(self, record):
        self.record = record

    @classmethod
    def from_aid(cls, aid):
        record = json.loads(request(aid, 'aid', 'assay'))['PC_AssayContainer'][0]
        return cls(record)

    @property
    def aid(self):
        return self.record['id']['id']['aid']


class PubChemHTTPError(Exception):
    """ Generic error class to handle all HTTP error codes """
    def __init__(self, e):
        self.code = e.code
        self.msg = e.reason
        try:
            self.msg += ': %s' % json.load(e)['Fault']['Details'][0]
        except (ValueError, IndexError, KeyError):
            pass
        if self.code == 400:
            raise BadRequestError(self.msg)
        elif self.code == 404:
            raise NotFoundError(self.msg)
        elif self.code == 405:
            raise MethodNotAllowedError(self.msg)
        elif self.code == 504:
            raise TimeoutError(self.msg)
        elif self.code == 501:
            raise UnimplementedError(self.msg)
        elif self.code == 500:
            raise ServerError(self.msg)

    def __str__(self):
        return repr(self.msg)

class BadRequestError(PubChemHTTPError):
    """ Request is improperly formed (syntax error in the URL, POST body, etc.) """
    def __init__(self, msg='Request is improperly formed'):
        self.msg = msg

class NotFoundError(PubChemHTTPError):
    """ The input record was not found (e.g. invalid CID) """
    def __init__(self, msg='The input record was not found'):
        self.msg = msg

class MethodNotAllowedError(PubChemHTTPError):
    """ Request not allowed (such as invalid MIME type in the HTTP Accept header) """
    def __init__(self, msg='Request not allowed'):
        self.msg = msg

class TimeoutError(PubChemHTTPError):
    """ The request timed out, from server overload or too broad a request """
    def __init__(self, msg='The request timed out'):
        self.msg = msg

class UnimplementedError(PubChemHTTPError):
    """ The requested operation has not (yet) been implemented by the server """
    def __init__(self, msg='The requested operation has not been implemented'):
        self.msg = msg

class ServerError(PubChemHTTPError):
    """ Some problem on the server side (such as a database server down, etc.) """
    def __init__(self, msg='Some problem on the server side'):
        self.msg = msg

if __name__ == '__main__':
    print get_synonyms('Aspirin', 'name', 'substance')