
import rasterio as rio
import rasterio.plot 
from pyproj import CRS
import requests
import pandas as pd
import rasterio.mask

## Input address and get point and shape coordinates 

address = input("Enter the Flander address: ") 

def get_details(address: str):
    req = requests.get(f"https://loc.geopunt.be/v4/Location?q={address}").json()
    info = {'address' : address, 
                'x_value' : req['LocationResult'][0]['Location']['X_Lambert72'],
                'y_value' : req['LocationResult'][0]['Location']['Y_Lambert72'],
                'street' : req['LocationResult'][0]['Thoroughfarename'],
                'house_number' : req['LocationResult'][0]['Housenumber'], 
                'postcode': req['LocationResult'][0]['Zipcode'], 
                'municipality' : req['LocationResult'][0]['Municipality']}
    
    detail = requests.get("https://api.basisregisters.vlaanderen.be/v1/adresmatch", 
                          params={"postcode": info['postcode'], 
                                  "straatnaam": info['street'],
                                  "huisnummer": info['house_number']}).json()
    building = requests.get(detail['adresMatches'][0]['adresseerbareObjecten'][0]['detail']).json()
    build = requests.get(building['gebouw']['detail']).json()
    info['polygon'] = [build['geometriePolygoon']['polygon']]
    
    return info
address_info = get_details(address)
print(address_info)

xx = address_info["x_value"]
yy = address_info["y_value"]
coords = address_info['polygon']


## Identify geotif files of DSM and DTM where the house exists from saved bound box file 

df_bounds = pd.read_csv("/home/anjali/Becode_projects/3D-House-project/bounding_box.csv",sep =";")

for i in range(0,43):
    if df_bounds.iloc[i]["left"] <= xx <= df_bounds.iloc[i]["right"] and df_bounds.iloc[i]["bottom"] <= yy <= df_bounds.iloc[i]["top"]:
        dsm_file = df_bounds.iloc[i]["file_name_dsm"]
        dtm_file = df_bounds.iloc[i]["file_name_dtm"]
        print(dsm_file)  
        print(dtm_file)


# Read that particular DSM and DTM file
DSM = rio.open(f"zip+https://downloadagiv.blob.core.windows.net/dhm-vlaanderen-ii-dsm-raster-1m/{dsm_file }.zip!/GeoTIFF/{dsm_file }.tif")
print(DSM.bounds)

DTM = rio.open(f"zip+https://downloadagiv.blob.core.windows.net/dhm-vlaanderen-ii-dtm-raster-1m/{dtm_file }.zip!/GeoTIFF/{dtm_file }.tif")
print(DTM.bounds)

## Croping the house from DSM and DTM file using shape coordinates 

DSM_out_img,DSM_out_transform  = rasterio.mask.mask(DSM, shapes=coords, crop=True, filled = True)
DSM_out_meta = DSM.meta.copy()
DSM_out_meta.update({"driver": "GTiff","height": DSM_out_img.shape[1],"width": DSM_out_img.shape[2],"transform": DSM_out_transform,"crs": CRS.from_epsg(31370)})

DSM_out_tif = r"/home/anjali/Becode_projects/3D-House-project/DSM/Masked_DSM.tif"
with rasterio.open(DSM_out_tif, "w", **DSM_out_meta) as dest:
    dest.write(DSM_out_img)

DSM_clipped = rasterio.open(DSM_out_tif)
rasterio.plot.show(DSM_clipped, title = "DSM_clipped")


DTM_out_img,DTM_out_transform  = rasterio.mask.mask(DTM, shapes=coords, crop=True, filled = True)
DTM_out_meta = DTM.meta.copy()
DTM_out_meta.update({"driver": "GTiff","height": DTM_out_img.shape[1],"width": DTM_out_img.shape[2],"transform": DTM_out_transform,"crs": CRS.from_epsg(31370)})

DTM_out_tif = r"/home/anjali/Becode_projects/3D-House-project/DTM/Masked_DTM.tif"
with rasterio.open(DTM_out_tif, "w", **DTM_out_meta) as dest:
    dest.write(DTM_out_img)

DTM_clipped = rasterio.open(DTM_out_tif)
rasterio.plot.show(DTM_clipped, title = "DTM_clipped")


## Calculate area of house 

import geopandas
from geopandas import GeoSeries
from shapely.geometry import Polygon
#Get building polygon coordinates
polygon = address_info['polygon']

#Convert polygon to more useful geopanda series
t = []

#Get coordinates
for i in polygon[0]['coordinates'][0]:
    t.append(tuple(i))

#Convert coordinates to Polygon format
global house_polygon
house_polygon = Polygon(t)

#Save Polygon in geopanda series
global gpd_df
gpd_df = GeoSeries([house_polygon])

#Get area of building
global house_area
#Area of the building
house_area = gpd_df.area

area = round(int(house_area), 1)
print('The building floor area is:', area, 'sq meters')
    

## Plot 3D house 


import rioxarray

dsm_img = rioxarray.open_rasterio("/home/anjali/Becode_projects/3D-House-project/DSM/Masked_DSM.tif")
dtm_img = rioxarray.open_rasterio("/home/anjali/Becode_projects/3D-House-project/DTM/Masked_DTM.tif")

#Canopy height model calculation
chm = dsm_img - dtm_img



import plotly.graph_objects as go

fig = go.Figure(data=[go.Surface(z=chm[0])])


## Update title and axis labels
fig.update_layout(
    title={
        'text': f"""<b>3D House</b><br><b>{address}</b>
        <br>X and Y coordinates (Lambert 72 system): 
        [{xx}, {yy}]</b>
        <br>Area of building = {area} Sq.m""",
        'y':0.95,
        'x':0.5,
        'xanchor': 'center',
        'yanchor': 'top'}
        )
fig.update_layout(
    scene=dict(
        xaxis_title='X: Distance (meter)',
        yaxis_title='Y: Distance (meter)',
        zaxis_title='Z: Height (meter)'
    ),
    legend_title="Height",
    font=dict(
        family="Roboto, monospace",
        size=10,
        color="black"
    )
)
fig.show()
