import fs from "fs";
import {IfcAPI,IFCFLOWTERMINAL,IFCWALL,IFCWINDOW,IFCDOOR,IFCROOF,IFCMATERIAL,IFCMATERIALDEFINITION,IFCMATERIALLAYERSET,IFCMATERIALLAYER,IFCMATERIALPROFILE,IFCMATERIALPROFILESET,IFCMATERIALCONSTITUENTSET,IFCMATERIALCONSTITUENT,IFC4} from "web-ifc";
const createCsvWriter = require('csv-writer').createObjectCsvWriter;
const csvWriter = createCsvWriter({
    path: './output.csv',
    header: [
        {id: 0, title: 'Name'},
        {id: 1, title: 'ExpressID'},
        {id: 2, title: 'Volume'}
    ]
});

const ifcapi = new IfcAPI();
let doneDefinitions = new Set();

function checkToProcess(definition: any, expressID:number) :boolean {
    return definition.Material.expressID==expressID && !doneDefinitions.has(definition.expressID);
}

async function parseLayerSet(definition:any,expressID:number) {
    let totalLayerThicknesses = 0;
    let targetRatio=0;

    for (let layer of definition.MaterialLayers) totalLayerThicknesses += layer.LayerThickness.value;

    let totalOfMaterial = 0;
    for (let layer of definition.MaterialLayers) {
        if (layer.Material.expressID==expressID) totalOfMaterial += layer.LayerThickness.value;
    }   
    
    targetRatio =  totalOfMaterial/totalLayerThicknesses;  
    return targetRatio* (await volumeOfAssociated(definition.AssociatedTo as IFC4.IfcRelAssociatesMaterial[]));
}

async function parseProfile(definition:IFC4.IfcMaterialProfile,expressID:number) {
    let volume = 0;
    let noProfiles = 1;
    if (checkToProcess(definition,expressID)) {
        doneDefinitions.add(definition.expressID);
        definition = ifcapi.GetLine(0,definition.expressID,true,true);
        if (definition.AssociatedTo?.length==0) {
            let parent = ifcapi.GetLine(0,(definition.ToMaterialProfileSet as IFC4.IfcMaterialProfileSet).expressID,true,true);
            definition.AssociatedTo = parent.AssociatedTo;    
        }
        volume+=(await volumeOfAssociated(definition.AssociatedTo as IFC4.IfcRelAssociatesMaterial[]))/noProfiles;
    }
    return volume;
}

async function parseConstituent(definition:IFC4.IfcMaterialConstituent,expressID:number) {
    let volume = 0;
    let noConstituents = 1;
    let constituentSet = definition?.ToMaterialConstituentSet as IFC4.IfcMaterialConstituentSet;
    
    if (checkToProcess(definition,expressID)) {
        doneDefinitions.add(definition.expressID);
        definition = ifcapi.GetLine(0,definition.expressID,true,true);
        if (definition.AssociatedTo?.length==0) {
            let parent = ifcapi.GetLine(0,(definition.ToMaterialConstituentSet as IFC4.IfcMaterialConstituentSet).expressID,true,true);
            definition.AssociatedTo = parent.AssociatedTo;    
        }
        volume+= await volumeOfAssociated(definition.AssociatedTo as IFC4.IfcRelAssociatesMaterial[]) / noConstituents;
    }
    return volume;
}

function getFlexValue(item:any){
    let value:string = Object.keys(item).find(x=> x.includes('Value')) as string;
    return item[value].value;
}

async function getPSetVolume(actualObject: any, pSetName: string, propName:string) {
    let pSets = await ifcapi.properties.getPropertySets(0,actualObject.expressID,true);
        for (let pSet of pSets) {
            if (pSetName=="" && pSet.constructor.name =="IfcElementQuantity") {
                for (let quan of pSet.Quantities) if (quan.Name.value==propName ) return getFlexValue(quan);
            } else if (pSet.Name.value==pSetName) {
                for (let prop of pSet.HasProperties) {
                    if (prop.Name.value==propName) {
                        return getFlexValue(prop);
                    }
                }
            }
        }
    return 0;
}

async function volumeOfObject(actualObject: any) {
    if (actualObject.type==IFCDOOR || actualObject.type==IFCWINDOW) {
       let volume = await getPSetVolume(actualObject,"Dimensions","GrossVolume");
       if (volume ==0) volume = await getPSetVolume(actualObject,"Dimensions","Volume");
       if (volume ==0) return (60/1000)*(actualObject.OverallHeight.value/1000)+(actualObject.OverallWidth.value/1000);
       return volume;
    }
    if (actualObject.type==IFCROOF) {
        let volume = await getPSetVolume(actualObject,"Dimensions","GrossVolume");
        if (volume ==0) volume = await getPSetVolume(actualObject,"Dimensions","Volume");
        if (volume ==0) volume = (await getPSetVolume(actualObject,"","GrossArea"))*0.005;
        if (volume ==0) volume = (await getPSetVolume(actualObject,"","ProjectedArea"))*0.005;
        return volume;
    }
    
    let volume = await getPSetVolume(actualObject,"Dimensions","GrossVolume");
    if (volume ==0) volume = await getPSetVolume(actualObject,"Dimensions","Volume");
    if (volume == 0) volume = (await getPSetVolume(actualObject,"","GrossVolume"));
    if (volume > 0) return volume;
    console.log(actualObject.constructor.name+"("+actualObject.expressID+")Not Implemented");
    return 0;
}

async function volumeOfAssociated(associates: IFC4.IfcRelAssociatesMaterial[]):Promise<number> {
    if (associates==null) return 0;
    let volume = 0;
    for (let x=0; x < associates.length;x++) {
        for (let y=0; y < associates[x].RelatedObjects.length;y++){
            let actualObject = ifcapi.GetLine(0,(associates[x].RelatedObjects[y] as any).value,true,true);
            if (actualObject.constructor.name.includes("Type")) {
                for (let i=0; i < actualObject.Types.length;i++) {
                    for (let j=0; j < actualObject.Types[i].RelatedObjects.length;j++) {
                        let innerObject = ifcapi.GetLine(0,actualObject.Types[i].RelatedObjects[j].value,true,true);
                        volume += await volumeOfObject(innerObject)
                    }
                }
            } else volume+= await volumeOfObject(actualObject);
        }
    }
    return volume;
}
console.log("reading:"+process.argv[2])

ifcapi.Init().then(async () => {;

    let data = [];
    console.log("reading:"+process.argv[1])
    let modelID = ifcapi.OpenModel(fs.readFileSync(process.argv[2]));

    let materials = ifcapi.GetLineIDsWithType(modelID,IFCMATERIAL,true);
    let materialDefinitionIds = ifcapi.GetLineIDsWithType(modelID,IFCMATERIALDEFINITION,true);
    let materialDefinitions = [];
    for (let i=0; i < materialDefinitionIds.size();i++) materialDefinitions.push(ifcapi.GetLine(modelID,materialDefinitionIds.get(i),true,true));
    for (let i=0; i < materials.size();i++) {
        let thisMaterialData = [];
        let expressID=materials.get(i);
        let materialData = ifcapi.GetLine(modelID,expressID,true,true);
        let associations = materialData.AssociatedTo;
        thisMaterialData[0]=materialData.Name.value;
        thisMaterialData[1]=expressID;
        thisMaterialData[2]=0;
        for (let x=0; x < materialDefinitions.length;x++) {
            let definition = materialDefinitions[x];
            if (definition.type == IFCMATERIALLAYERSET)  thisMaterialData[2]+= await parseLayerSet(definition,expressID);
            else if (definition.type == IFCMATERIALPROFILE)  thisMaterialData[2]+= await parseProfile(definition,expressID);
            else if (definition.type == IFCMATERIALPROFILESET) for (let profile of definition.MaterialProfiles)  thisMaterialData[2] += await parseProfile(profile,expressID);
            else if (definition.type == IFCMATERIALCONSTITUENT)  thisMaterialData[2]+= await parseConstituent(definition,expressID);
            else if (definition.type == IFCMATERIALCONSTITUENTSET) for (let constituent of definition.MaterialConstituents)  thisMaterialData[2] += await parseConstituent(constituent,expressID);
        }
        thisMaterialData[2]+=await volumeOfAssociated(materialData.AssociatedTo)
        
        data.push(thisMaterialData);
    }

    csvWriter.writeRecords(data)

});