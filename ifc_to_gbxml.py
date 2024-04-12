# Import necessary python libraries e.g. IfcOpenShell, PythonOCC and MiniDom
import ifcopenshell.geom
import OCC.Core.BRep
import OCC.Core.TopExp
import OCC.Core.TopoDS
import OCC.Core.TopAbs
import OCC.Core.ProjLib
import OCC.Core.BRepTools
import datetime
import time
import re
import sys
from xml.dom import minidom

# Use IfcOpenShell and OPENCASCADE to convert implicit geometry into explicit geometry
# Each Face consists of Wires, which consists of Edges, which has Vertices
FACE, WIRE, EDGE, VERTEX = OCC.Core.TopAbs.TopAbs_FACE, OCC.Core.TopAbs.TopAbs_WIRE, OCC.Core.TopAbs.TopAbs_EDGE, \
                           OCC.Core.TopAbs.TopAbs_VERTEX

settings = ifcopenshell.geom.settings()
settings.set(settings.USE_PYTHON_OPENCASCADE, True)

def createRegtangularGeometry(item, related,root):
    geometry = root.createElement('RectangularGeometry')
    width=root.createElement("Width")
    width.appendChild(root.createTextNode("0"))
    height=root.createElement("Height")
    height.appendChild(root.createTextNode("0"))
    #geometry.appendChild(width)
    #geometry.appendChild(height)
    item.appendChild(geometry)

def sub(shape, ty):
    F = {
        OCC.Core.TopAbs.TopAbs_FACE: OCC.Core.TopoDS.topods_Face,
        OCC.Core.TopAbs.TopAbs_WIRE: OCC.Core.TopoDS.topods_Wire,
        OCC.Core.TopAbs.TopAbs_EDGE: OCC.Core.TopoDS.topods_Edge,
        OCC.Core.TopAbs.TopAbs_VERTEX: OCC.Core.TopoDS.topods_Vertex,
    }[ty]
    exp = OCC.Core.TopExp.TopExp_Explorer(shape, ty)
    while exp.More():
        face = F(exp.Current())
        yield face
        exp.Next()


def ring(wire, face):
    def vertices():
        exp = OCC.Core.BRepTools.BRepTools_WireExplorer(wire, face)
        while exp.More():
            yield exp.CurrentVertex()
            exp.Next()
        yield exp.CurrentVertex()

    return list(map(lambda p: (p.X(), p.Y(), p.Z()), map(OCC.Core.BRep.BRep_Tool.Pnt, vertices())))


# Face to vertices
def get_vertices(shape):
    for face in sub(shape, FACE):
        for idx, wire in enumerate(sub(face, WIRE)):
            vertices = ring(wire, face)

            if idx > 0:
                vertices.reverse()
            return vertices


# Align the gbXML input according to the predefined official gbXML schema
def fix_xml(a):
    return a.replace('$', '').replace(':', '').replace(' ', '').replace('(', '').replace(')', '').replace('\\','').replace('/','').replace('.','_')

# check if one of the material types we recogn
def get_materials(m):
    materials = []
    if m.is_a('IfcMaterialLayerSetUsage'):
        materialsTmp = m.ForLayerSet.MaterialLayers
        for mi in materialsTmp:
            materials.append(mi)
    elif m.is_a('IfcMaterialLayerSet'):
        materialsTmp = m.MaterialLayers
        for mi in materialsTmp:
            materials.append(mi)
    elif m.is_a('IfcMaterialLayer'):
        materials.append(m)
    return materials

# Access the specific IFC file; external directory: (r"C:/Users/s136146/Desktop/StoreysWindowsMaterialsFacade.ifc")
ifc_file = ifcopenshell.open(sys.argv[1])

# Create the XML root by making use of MiniDom
root = minidom.Document()

# Create the 'gbXML' element and append it to the Root of the document
gbxml = root.createElement('gbXML')
root.appendChild(gbxml)

# Create attributes for the 'gbXML' element
gbxml.setAttribute('xmlns', 'http://www.gbxml.org/schema')
gbxml.setAttribute('temperatureUnit', 'C')
gbxml.setAttribute('lengthUnit', 'Meters')
gbxml.setAttribute('areaUnit', 'SquareMeters')
gbxml.setAttribute('volumeUnit', 'CubicMeters')
gbxml.setAttribute('useSIUnitsForResults', 'true')
gbxml.setAttribute('version', '0.37')

# Create a dictionary to store all gbXML element Id's
dict_id = {}

# Specify the 'Campus' element of the gbXML schema; making use of IFC entity 'IfcSite'
# This element is added as child to the earlier created 'gbXML' element
site = ifc_file.by_type('IfcSite')
for element in site:
    campus = root.createElement('Campus')
    campus.setAttribute('id', fix_xml(element.GlobalId))
    gbxml.appendChild(campus)

    dict_id[fix_xml(element.GlobalId)] = campus

    # Specify the 'Location' element of the gbXML schema; making use of IFC entities 'IfcSite' and 'IfcPostalAddress'
    # This new element is added as child to the earlier created 'Campus' element
    location = root.createElement('Location')
    campus.appendChild(location)

    longitude = root.createElement('Longitude')
    longitudeValue = str(element.RefLongitude[0])
    longitude.appendChild(root.createTextNode(longitudeValue))
    location.appendChild(longitude)

    latitude = root.createElement('Latitude')
    latitudeValue = str(element.RefLatitude[0])
    latitude.appendChild(root.createTextNode(latitudeValue))
    location.appendChild(latitude)

    elevation = root.createElement('Elevation')
    elevation.appendChild(root.createTextNode(str(element.RefElevation)))
    location.appendChild(elevation)

address = ifc_file.by_type('IfcPostalAddress')
for element in address:
    zipcode = root.createElement('ZipcodeOrPostalCode')
    zipcode.appendChild(root.createTextNode(element.PostalCode))
    location.appendChild(zipcode)

    name = root.createElement('Name')
    name.appendChild(root.createTextNode(element.Region + ', ' + element.Country))
    location.appendChild(name)

# Specify the 'Building' element of the gbXML schema; making use of IFC entity 'IfcBuilding'
# This new element is added as child to the earlier created 'Campus' element
buildings = ifc_file.by_type('IfcBuilding')
for element in buildings:
    building = root.createElement('Building')
    building.setAttribute('id', fix_xml(element.GlobalId))
    building.setAttribute('buildingType', "Unknown")
    campus.appendChild(building)

    dict_id[fix_xml(element.GlobalId)] = building

for element in address:
    streetAddress = root.createElement('StreetAddress')
    streetAddress.appendChild(root.createTextNode(element.Region + ', ' + element.Country))
    building.appendChild(streetAddress)

# Specify the 'BuildingStorey' element of the gbXML schema; making use of IFC entity 'IfcBuildingStorey'
# This new element is added as child to the earlier created 'Building' element
storeys = ifc_file.by_type('IfcBuildingStorey')
storey_name = 1
for element in storeys:
    buildingStorey = root.createElement('BuildingStorey')
    myStoreyName = element.LongName
    if myStoreyName == None:
        myStoreyName = storey_name
    buildingStorey.setAttribute('ifcGUID', fix_xml(element.GlobalId))
    buildingStorey.setAttribute('id', fix_xml(myStoreyName))
    building.appendChild(buildingStorey)

    dict_id[fix_xml(element.GlobalId)] = buildingStorey

    name = root.createElement('Name')
    name.appendChild(root.createTextNode('%s' % myStoreyName))
    storey_name = storey_name + 1
    buildingStorey.appendChild(name)

    level = root.createElement('Level')
    level.appendChild(root.createTextNode(str(element.Elevation/1000)))
    buildingStorey.appendChild(level)

#load zones
zoneAssignemnts = {}

zones = ifc_file.by_type('IfcZone')
for z in zones:
    zone = root.createElement('Zone')
    myZoneName = fix_xml(z.Name)
    if myZoneName == None:
        myZoneName = fix_xml(z.GlobalId)
    zone.setAttribute('ifcGUID', fix_xml(z.GlobalId))
    zone.setAttribute('id', myZoneName)
    gbxml.appendChild(zone)
    name = root.createElement('Name')
    name.appendChild(root.createTextNode('%s' % myZoneName))
    zone.appendChild(name);
    TypeCode = root.createElement('TypeCode')
    TypeCode.appendChild(root.createTextNode('10'))
    zone.appendChild(TypeCode);
    for g in z.IsGroupedBy:
        for s in g.RelatedObjects:
            zoneAssignemnts[s.GlobalId]=myZoneName
            
# Specify the 'Space' element of the gbXML schema; making use of IFC entity 'IfcSpace'
# This new element is added as child to the earlier created 'Building' element
spaces = ifc_file.by_type('IfcSpace')
space_name = 1
for s in spaces:
    space = root.createElement('Space')
    mySpaceName = fix_xml(s.LongName)
    if mySpaceName == None:
        mySpaceName = fix_xml(s.GlobalId)
    space.setAttribute('ifcGUID', fix_xml(s.GlobalId))
    space.setAttribute('id', mySpaceName)

    dict_id[fix_xml(s.GlobalId)] = space

    # Refer to the relating 'BuildingStorey' GUID by iterating through IFC entities
    space.setAttribute('buildingStoreyIdRef', fix_xml(s.Decomposes[0].RelatingObject.LongName))

    area = root.createElement('Area')
    volume = root.createElement('Volume')
            

    properties = s.IsDefinedBy
    gotSpaceType = False
    for r in properties:
        if r.is_a('IfcRelDefinesByProperties'):
            if r.RelatingPropertyDefinition.is_a('IfcPropertySet'):
                for p in r.RelatingPropertyDefinition.HasProperties:
                    if p.Name == 'Area':
                        valueArea = p.NominalValue.wrappedValue
                        area.appendChild(root.createTextNode(str(valueArea)))
                        space.appendChild(area)
                    if p.Name == 'Volume':
                        valueVolume = p.NominalValue.wrappedValue
                        volume.appendChild(root.createTextNode(str(valueVolume)))
                        space.appendChild(volume)
                    if p.Name == 'Space Type':
                        valueType = p.NominalValue.wrappedValue
                        valueType = re.sub('[^0-9a-zA-Z]+', '', valueType)
                        space.setAttribute('spaceType', valueType)
                        gotSpaceType = True

    if gotSpaceType == True:
        building.appendChild(space)
    else:
        continue
    
    if s.GlobalId in zoneAssignemnts:
        space.setAttribute('zoneIdRef',zoneAssignemnts[s.GlobalId])
    else:
        print("Space not in zone!!! "+s.GlobalId+"("+s.LongName+")")
            
    name = root.createElement('Name')
    name.appendChild(root.createTextNode('%s' % mySpaceName))
    space_name = space_name + 1
    space.appendChild(name)

    # Specify the 'SpaceBoundary' element of the gbXML schema; making use of IFC entity 'IfcSpace'
    # This new element is added as child to the earlier created 'Space' element
    boundaries = s.BoundedBy
    for element in boundaries:

        # Make sure a 'SpaceBoundary' is representing an actual element
        if element.RelatedBuildingElement == None:
            continue

        # Specify the 'IfcCurveBoundedPlane' entity which represents the geometry
        boundaryGeom = element.ConnectionGeometry.SurfaceOnRelatingElement

        if boundaryGeom.is_a('IfcCurveBoundedPlane') and boundaryGeom.InnerBoundaries is None:
            boundaryGeom.InnerBoundaries = ()

        #print(boundaryGeom)

        # Use IfcOpenShell and OPENCASCADE to attach geometry to the specified IFC entity
        space_boundary_shape = ifcopenshell.geom.create_shape(settings, boundaryGeom)

        # Create 'SpaceBoundary' elements for the following building elements
        if element.RelatedBuildingElement.is_a('IfcCovering') or element.RelatedBuildingElement.is_a('IfcSlab') or \
                element.RelatedBuildingElement.is_a('IfcWall') or element.RelatedBuildingElement.is_a('IfcRoof'):

            spaceBoundary = root.createElement('SpaceBoundary')
            spaceBoundary.setAttribute('isSecondLevelBoundary', "true")

            # Refer to the relating 'SpaceBoundary' GUID by iterating through IFC entities
            spaceBoundary.setAttribute('surfaceIdRef', fix_xml(element.GlobalId))

            space.appendChild(spaceBoundary)

            planarGeometry = root.createElement('PlanarGeometry')
            spaceBoundary.appendChild(planarGeometry)

            # Specify the 'PolyLoop' element which contains 4 'CartesianPoint' elements with each
            # 3 explicit 'Coordinate' elements. Note: if geometry is not attached to the 'SpaceBoundary' element, the
            # relationship between 'Space' and 'Building' elements is handled only on a logical level. If geometry is
            # attached, it is given within the local coordinate systems of the 'Space' and (if given in addition) of the
            # 'Building' element.

            # Z-coordinates are extracted by iterating through IFC entities to the 'IfcCartesianPoint' of the
            # related 'IfcBuildingStorey'
            #print('SpaceBoundary')

            new_z = element.RelatingSpace.ObjectPlacement.PlacementRelTo.RelativePlacement.Location.Coordinates[2]/1000
            #print("Z:"+str(new_z))
            

            polyLoop = root.createElement('PolyLoop')

            for v in get_vertices(space_boundary_shape):
                x, y, z = v
                z = z + new_z
                #print(x, y, z)

                point = root.createElement('CartesianPoint')

                for c in x, y, z:
                    coord = root.createElement('Coordinate')
                    coord.appendChild(root.createTextNode(str(c)))
                    point.appendChild(coord)

                polyLoop.appendChild(point)

            planarGeometry.appendChild(polyLoop)

# Specify the 'Surface' element of the gbXML schema; making use of IFC entity 'IfcRelSpaceBoundary'
# This new element is added as child to the earlier created 'Campus' element
boundaries = ifc_file.by_type('IfcRelSpaceBoundary')
opening_id = 1
for element in boundaries:
    # Make sure a 'SpaceBoundary' is representing an actual element
    if element.RelatedBuildingElement == None:
        continue

    # Specify the 'IfcCurveBoundedPlane' entity which represents the geometry
    if element.ConnectionGeometry.SurfaceOnRelatingElement == None:
        continue

    surfaceGeom = element.ConnectionGeometry.SurfaceOnRelatingElement

    if surfaceGeom.is_a('IfcCurveBoundedPlane') and surfaceGeom.InnerBoundaries is None:
        surfaceGeom.InnerBoundaries = ()

    #print(surfaceGeom)

    space_boundary_shape = ifcopenshell.geom.create_shape(settings, surfaceGeom)
    #print(space_boundary_shape)

    # Specify each 'Surface' element and set 'SurfaceType' attributes
    if element.RelatedBuildingElement.is_a('IfcCovering') or element.RelatedBuildingElement.is_a('IfcSlab') or element.\
            RelatedBuildingElement.is_a('IfcWall') or element.RelatedBuildingElement.is_a('IfcRoof'):

        surface = root.createElement('Surface')
        createRegtangularGeometry(surface,element.RelatedBuildingElement,root)
        surface.setAttribute('id', fix_xml(element.GlobalId))
        
        twoSpace = False
        
        dict_id[fix_xml(element.GlobalId)] = surface

        if element.RelatedBuildingElement.is_a('IfcCovering'):
            surface.setAttribute('surfaceType', 'Ceiling')
            twoSpace = True

        if element.RelatedBuildingElement.is_a('IfcSlab'):
            surface.setAttribute('surfaceType', 'InteriorFloor')
            twoSpace = True
            
        if element.RelatedBuildingElement.is_a('IfcWall') and element.\
                InternalOrExternalBoundary == 'EXTERNAL':
            surface.setAttribute('surfaceType', 'ExteriorWall')

        if element.RelatedBuildingElement.is_a('IfcWall') and element.\
                InternalOrExternalBoundary == 'INTERNAL':
            surface.setAttribute('surfaceType', 'InteriorWall')
            twoSpace = True

        if element.RelatedBuildingElement.is_a('IfcRoof'):
            surface.setAttribute('surfaceType', 'Roof')

        
        # Refer to the relating 'IfcRelAssociatesMaterial' GUID by iterating through IFC entities
        construction =  get_materials(element.RelatedBuildingElement.HasAssociations[0].RelatingMaterial)[0]
        surface.setAttribute('constructionIdRef', fix_xml(str(construction.id())))

        name = root.createElement('Name')
        name.appendChild(root.createTextNode(fix_xml(element.GlobalId)))

        surface.appendChild(name)

        #if twoSpace == True:
        #    print("GOT "+str(len(element.RelatedBuildingElement.ProvidesBoundaries))+" SPACES")
            
        adjacentSpaceId = root.createElement('AdjacentSpaceId')

        # Refer to the relating 'Space' GUID by iterating through IFC entities
        adjacentSpaceId.setAttribute('spaceIdRef', fix_xml(element.RelatingSpace.LongName))
        surface.appendChild(adjacentSpaceId)

        planarGeometry = root.createElement('PlanarGeometry')
        surface.appendChild(planarGeometry)

        # Specify the 'PolyLoop' element which contains 4 'CartesianPoint' elements with each
        # 3 explicit 'Coordinate' elements. Note: if geometry is not attached to the 'SpaceBoundary' element, the
        # relationship between 'Space' and 'Building' elements is handled only on a logical level. If geometry is
        # attached, it is given within the local coordinate systems of the 'Space' and (if given in addition) of the
        # 'Building' element.

        # Z-coordinates are extracted by iterating through IFC entities to the 'IfcCartesianPoint' of the
        # related 'IfcBuildingStorey'
        #print("Surface")

        new_z = element.RelatingSpace.ObjectPlacement.PlacementRelTo.RelativePlacement.Location.Coordinates[2]/1000


        polyLoop = root.createElement('PolyLoop')

        for v in get_vertices(space_boundary_shape):
            x, y, z = v
            z = z + new_z
            #print(x, y, z)

            point = root.createElement('CartesianPoint')

            for c in x, y, z:
                coord = root.createElement('Coordinate')
                coord.appendChild(root.createTextNode(str(c)))
                point.appendChild(coord)

            polyLoop.appendChild(point)

        planarGeometry.appendChild(polyLoop)

        objectId = root.createElement('CADObjectId')
        objectId.appendChild(root.createTextNode(fix_xml(element.GlobalId)))
        surface.appendChild(objectId)

        campus.appendChild(surface)

    if element.RelatedBuildingElement.is_a('IfcWindow'):
        opening = root.createElement('Opening')
        createRegtangularGeometry(opening,element.RelatedBuildingElement,root)

        # Refer to the relating 'IfcWindow' GUID by iterating through IFC entities
        opening.setAttribute('windowTypeIdRef', fix_xml(element.RelatedBuildingElement.GlobalId))
        opening.setAttribute('openingType', 'OperableWindow')

        opening.setAttribute('id', 'Opening%d' % opening_id)
        opening_id = opening_id + 1

        # If the building element is an 'IfcWindow' the gbXML element 'Opening' is added
        #print('Opening')
        planarGeometry = root.createElement('PlanarGeometry')
        opening.appendChild(planarGeometry)

        # Specify the 'PolyLoop' element which contains 4 'CartesianPoint' elements with each
        # 3 explicit 'Coordinate' elements. Note: if geometry is not attached to the 'SpaceBoundary' element, the
        # relationship between 'Space' and 'Building' elements is handled only on a logical level. If geometry is
        # attached, it is given within the local coordinate systems of the 'Space' and (if given in addition) of the
        # 'Building' element.

        # Z-coordinates are extracted by iterating through IFC entities to the 'IfcCartesianPoint' of the
        # related 'IfcBuildingStorey'
        polyLoop = root.createElement('PolyLoop')

        new_z = element.RelatingSpace.ObjectPlacement.PlacementRelTo.RelativePlacement.Location.Coordinates[2]/1000

        for v in get_vertices(space_boundary_shape):
            x, y, z = v
            z = z + new_z
            #print(x, y, z)

            point = root.createElement('CartesianPoint')

            for c in x, y, z:
                coord = root.createElement('Coordinate')
                coord.appendChild(root.createTextNode(str(c)))
                point.appendChild(coord)

            polyLoop.appendChild(point)

        planarGeometry.appendChild(polyLoop)

        name = root.createElement('Name')
        name.appendChild(root.createTextNode(fix_xml(element.RelatedBuildingElement.Name)))
        opening.appendChild(name)

        objectId = root.createElement('CADObjectId')
        objectId.appendChild(root.createTextNode(fix_xml(element.RelatedBuildingElement.Name)))
        opening.appendChild(objectId)

        surface.appendChild(opening)

    else:
        continue

# Specify the 'WindowType' element of the gbXML schema; making use of IFC entity 'IfcWindow'
# This new element is added as child to the earlier created 'gbXML' element
windows = ifc_file.by_type('IfcWindow')
for element in windows:
    if fix_xml(element.ObjectType) in dict_id:
        continue
    window = root.createElement('WindowType')
    window.setAttribute('id', fix_xml(element.ObjectType))
    gbxml.appendChild(window)

    dict_id[fix_xml(element.ObjectType)] = window

    name = root.createElement('Name')
    name.appendChild(root.createTextNode(fix_xml(element.ObjectType)))
    window.appendChild(name)

    description = root.createElement('Description')
    description.appendChild(root.createTextNode(fix_xml(element.ObjectType)))
    window.appendChild(description)

    # Specify analytical properties of the 'IfcWindow' by iterating through IFC entities
    analyticValue = element.IsDefinedBy

    u_value = root.createElement('U-value')
    for r in analyticValue:
        if r.is_a("IfcRelDefinesByProperties"):
            if r.RelatingPropertyDefinition.is_a('IfcPropertySet'):
                for p in r.RelatingPropertyDefinition.HasProperties:
                    if p.Name == 'ThermalTransmittance':
                        valueU = p.NominalValue.wrappedValue
                        u_value.setAttribute('unit', 'WPerSquareMeterK')
                        u_value.appendChild(root.createTextNode(str(valueU)))
                        window.appendChild(u_value)

    solarHeat = root.createElement('SolarHeatGainCoeff')
    visualLight = root.createElement('Transmittance')
    for r in analyticValue:
        if r.is_a('IfcRelDefinesByType'):
            if r.RelatingType.is_a('IfcWindowStyle'):
                for p in r.RelatingType.HasPropertySets:
                    if p.Name == 'Analytical Properties(Type)':
                        for t in p.HasProperties:
                            if t.Name == 'Solar Heat Gain Coefficient':
                                valueSolar = t.NominalValue.wrappedValue
                                solarHeat.setAttribute('unit', 'Fraction')
                                solarHeat.appendChild(root.createTextNode(str(valueSolar)))
                                window.appendChild(solarHeat)

                            if t.Name == 'Visual Light Transmittance':
                                valueLight = t.NominalValue.wrappedValue
                                visualLight.setAttribute('unit', 'Fraction')
                                visualLight.setAttribute('type', 'Visible')
                                visualLight.appendChild(root.createTextNode(str(valueLight)))
                                window.appendChild(visualLight)

# Specify the 'Construction' element of the gbXML schema; making use of IFC entity 'IfcRelSpaceBoundary'
# This new element is added as child to the earlier created 'gbXML' element
listCon = []

for element in boundaries:
    # Make sure a 'SpaceBoundary' is representing an actual element
    if element.RelatedBuildingElement is None:
        continue

    if element.RelatedBuildingElement.is_a('IfcCovering') or element.RelatedBuildingElement.is_a('IfcSlab') or element.\
            RelatedBuildingElement.is_a('IfcWall') or element.RelatedBuildingElement.is_a('IfcRoof'):

        # Refer to the relating 'IfcRelAssociatesMaterial' GUID by iterating through IFC entities
        constructions =  get_materials(element.RelatedBuildingElement.HasAssociations[0].RelatingMaterial)
        
        for constructionItem in constructions:
            # Make use of a list to make sure no same 'Construction' elements are added twice
            if constructionItem not in listCon:
                if fix_xml( str(element.RelatedBuildingElement.ObjectType)) in dict_id:
                    continue
                listCon.append(constructionItem)
                
            
                construction = root.createElement('Construction')
                construction.setAttribute('id', fix_xml( str(element.RelatedBuildingElement.ObjectType)))
                dict_id[fix_xml( str(element.RelatedBuildingElement.ObjectType))] = construction

                # Specify analytical properties of the 'Construction' element by iterating through IFC entities
                analyticValue = element.RelatedBuildingElement.IsDefinedBy

                u_value = root.createElement('U-value')
                for r in analyticValue:
                    if r.is_a('IfcRelDefinesByProperties'):
                        if r.RelatingPropertyDefinition.is_a('IfcPropertySet'):
                            for p in r.RelatingPropertyDefinition.HasProperties:
                                if element.RelatedBuildingElement.is_a("IfcWall"):
                                    if p.Name == 'ThermalTransmittance':
                                        valueU = p.NominalValue.wrappedValue
                                        u_value.setAttribute('unit', 'WPerSquareMeterK')
                                        u_value.appendChild(root.createTextNode(str(valueU)))
                                        construction.appendChild(u_value)

                                if p.Name == 'Heat Transfer Coefficient (U)':
                                    valueU = p.NominalValue.wrappedValue
                                    u_value.setAttribute('unit', 'WPerSquareMeterK')
                                    u_value.appendChild(root.createTextNode(str(valueU)))
                                    construction.appendChild(u_value)

                absorptance = root.createElement('Absorptance')
                for r in analyticValue:
                    if r.is_a('IfcRelDefinesByProperties'):
                        if r.RelatingPropertyDefinition.is_a('IfcPropertySet'):
                            for p in r.RelatingPropertyDefinition.HasProperties:
                                if p.Name == 'Absorptance':
                                    valueAb = p.NominalValue.wrappedValue
                                    absorptance.setAttribute('unit', 'Fraction')
                                    absorptance.setAttribute('type', 'ExtIR')
                                    absorptance.appendChild(root.createTextNode(str(valueAb)))
                                    construction.appendChild(absorptance)

                # Refer to the relating 'IfcRelAssociatesMaterial' GUID by iterating through IFC entities
                if element.RelatedBuildingElement.HasAssociations[0].RelatingMaterial.is_a('IfcMaterialLayerSetUsage'):
                    layerName =element.RelatedBuildingElement.HasAssociations[0].RelatingMaterial.ForLayerSet.LayerSetName
                else:
                    layerName = element.RelatedBuildingElement.HasAssociations[0].RelatingMaterial.LayerSetName
                
                layerId = fix_xml("layer_"+layerName)

                layer_id = root.createElement('LayerId')
                layer_id.setAttribute('layerIdRef', layerId)
                construction.appendChild(layer_id)

                # Refer to the relating 'IfcMaterialLayerSet' name by iterating through IFC entities
                name = root.createElement('Name')
                name.appendChild(root.createTextNode(constructionItem.Name))
                construction.appendChild(name)

                gbxml.appendChild(construction)

    else:
        continue

# Specify the 'Layer' element of the gbXML schema; making use of IFC entity 'IfcBuildingElement'
# This new element is added as child to the earlier created 'gbXML' element
buildingElements = ifc_file.by_type('IfcBuildingElement')
for element in buildingElements:
    if element.is_a('IfcWall') or element.is_a('IfcCovering') or element.is_a('IfcSlab') or element.is_a('IfcRoof'):

        # Try and catch an Element that is just an Aggregate
        if element.IsDecomposedBy:
            continue
        # Refer to the relating 'IfcRelAssociatesMaterial' GUID by iterating through IFC entities
        if not element.HasAssociations[0].RelatingMaterial.is_a('IfcMaterialLayerSetUsage') or element.HasAssociations[0].RelatingMaterial.is_a('IfcLayerSet'):
            continue
        name = ''
        if element.HasAssociations[0].RelatingMaterial.is_a('IfcMaterialLayerSetUsage'):
            name =element.HasAssociations[0].RelatingMaterial.ForLayerSet.LayerSetName
        else:
            name = element.HasAssociations[0].RelatingMaterial.LayerSetName
            
        layerId = fix_xml('layer_'+str(name))
        if layerId in dict_id:
            continue;
        layer = root.createElement('Layer')
        
        layer.setAttribute('id', layerId)

        dict_id[layerId] = layer

        # Specify the 'IfcMaterialLayer' entity and iterate to each 'IfcMaterial' entity
        
        nameElement = root.createElement('Name')
        nameElement.appendChild(root.createTextNode(str(name)))
        layer.appendChild(nameElement)
        
        materials = get_materials(element.HasAssociations[0].RelatingMaterial)
        matList = []
        for l in materials:
            if l.id() not in matList:
                material_id = root.createElement('MaterialId')
                material_id.setAttribute('materialIdRef', "mat_%d" % l.id())
                layer.appendChild(material_id)

                dict_id["mat_%d" % l.id()] = layer
                matList.append(l.id())

                gbxml.appendChild(layer)

    else:
        continue

# Specify the 'Material' element of the gbXML schema; making use of IFC entity 'IfcBuildingElement'
# This new element is added as child to the earlier created 'gbXML' element
listMat = []

for element in buildingElements:
    if element.is_a('IfcWall') or element.is_a("IfcSlab") or element.is_a('IfcCovering') or element.is_a('IfcRoof'):

        # Try and catch an Element that is just an Aggregate
        if element.IsDecomposedBy:
            continue
        materials =get_materials(element.HasAssociations[0].RelatingMaterial) 

        for l in materials:
            item = l.id()

            # Make use of a list to make sure no same 'Materials' elements are added twice
            if item not in listMat:
                listMat.append(item)

                material = root.createElement('Material')
                material.setAttribute('id', "mat_%d" % l.id())
                dict_id["mat_%d" % l.id()] = material

                name = root.createElement('Name')
                name.appendChild(root.createTextNode(l.Name))
                material.appendChild(name)

                if hasattr(l,'LayerThickness'):
                    thickness = root.createElement('Thickness')
                    thickness.setAttribute('unit', 'Meters')
                    valueT = l.LayerThickness
                    thickness.appendChild(root.createTextNode((str(valueT))))
                    material.appendChild(thickness)

                rValue = root.createElement('R-value')
                rValue.setAttribute('unit', 'SquareMeterKPerW')
                gbxml.appendChild(material)
                # Analytical properties of the Material entity can be found directly
                if hasattr(l, 'HasProperties'):
                    for material_property in l.HasProperties:
                        if material_property.Name == 'Pset_MaterialEnergy':
                            for pset_material_energy in material_property.Properties:
                                if pset_material_energy.Name == 'ThermalConductivityTemperatureDerivative':
                                    valueR = pset_material_energy.NominalValue.wrappedValue
                                    rValue.setAttribute('unit', 'SquareMeterKPerW')
                                    rValue.appendChild(root.createTextNode(str(valueR)))
                                    material.appendChild(rValue)


                # Specify analytical properties of the 'Material' element by iterating through IFC entities
                thermalResistance = element.IsDefinedBy
                for r in thermalResistance:
                    if r.is_a('IfcRelDefinesByType'):
                        if r.RelatingType.is_a('IfcWallType'):
                            for p in r.RelatingType.HasPropertySets:
                                if p.Name == 'Analytical Properties(Type)':
                                    for t in p.HasProperties:
                                        if t.Name == 'Heat Transfer Coefficient (U)':
                                            valueU = t.NominalValue.wrappedValue
                                            valueR = valueT / valueU
                                            rValue.appendChild(root.createTextNode(str(valueR)))
                                            material.appendChild(rValue)


                    if r.is_a('IfcRelDefinesByProperties'):
                        if r.RelatingPropertyDefinition.is_a('IfcPropertySet'):
                            for p in r.RelatingPropertyDefinition.HasProperties:
                                if p.Name == 'Heat Transfer Coefficient (U)':
                                    valueU = p.NominalValue.wrappedValue
                                    valueR = valueT / valueU
                                    rValue.setAttribute('unit', 'SquareMeterKPerW')
                                    rValue.appendChild(root.createTextNode(str(valueR)))
                                    material.appendChild(rValue)


                    if element.is_a('IfcCovering'):
                        if r.is_a('IfcRelDefinesByProperties'):
                            if r.RelatingType.is_a('IfcPropertySet'):
                                for p in r.RelatingType.HasPropertySets:
                                    if p.Name == 'Analytical Properties(Type)':
                                        for t in p.HasProperties:
                                            if t.Name == 'Heat Transfer Coefficient (U)':
                                                valueU = t.NominalValue.wrappedValue
                                                valueR = valueT / valueU
                                                rValue.setAttribute('unit', 'SquareMeterKPerW')
                                                rValue.appendChild(root.createTextNode(str(valueR)))
                                                material.appendChild(rValue)


    else:
        continue

# Specify the 'DocumentHistory' element of the gbXML schema; making use of IFC entity 'IfcApplication' and 'IfcPerson'
# This new element is added as child to the earlier created 'gbXML' element
programInfo = ifc_file.by_type('IfcApplication')
docHistory = root.createElement('DocumentHistory')
for element in programInfo:
    program = root.createElement('ProgramInfo')
    program.setAttribute('id', element.ApplicationIdentifier)
    docHistory.appendChild(program)

    company = root.createElement('CompanyName')
    company.appendChild(root.createTextNode(element.ApplicationDeveloper.Name))
    program.appendChild(company)

    product = root.createElement('ProductName')
    product.appendChild(root.createTextNode(element.ApplicationFullName))
    program.appendChild(product)

    version = root.createElement('Version')
    version.appendChild(root.createTextNode(element.Version))
    program.appendChild(version)

personInfo = ifc_file.by_type('IfcPerson')
for element in personInfo:
    created = root.createElement('CreatedBy')
    created.setAttribute('personId', element.GivenName)

for element in programInfo:
    created.setAttribute('programId', element.ApplicationIdentifier)

    today = datetime.date.today()
    created.setAttribute('date', today.strftime('%Y-%m-%dT') + time.strftime('%H:%M:%S'))
    docHistory.appendChild(created)

for element in personInfo:
    person = root.createElement('PersonInfo')
    person.setAttribute('id', element.GivenName)
    docHistory.appendChild(person)

gbxml.appendChild(docHistory)

# Create a new XML file and write all created elements to it
save_path_file = "New_Exported_gbXML.xml"

root.writexml( open(save_path_file, "w"),
               indent="  ",
               addindent="  ",
               newl='\n')
