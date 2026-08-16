import json
import geopandas as gpd
from shapely.geometry import Polygon
from japan_basic_section.grid import Grid

print("1/50,000図郭の生成中...")
g50k = Grid(system_number=7, level=50000)
gdf_50k = g50k.make_grid()
gdf_50k.set_crs(epsg=6675, inplace=True)

sub_polys = []
sub_codes = []

for idx in range(len(gdf_50k)):
    code = gdf_50k.index[idx]
    geom = gdf_50k.geometry.iloc[idx]
    minx, miny, maxx, maxy = geom.bounds
    midx = (minx + maxx) / 2.0
    midy = (miny + maxy) / 2.0
    
    # 1: NW, 2: NE, 3: SW, 4: SE
    p1 = Polygon([(minx, midy), (midx, midy), (midx, maxy), (minx, maxy)])
    p2 = Polygon([(midx, midy), (maxx, midy), (maxx, maxy), (midx, maxy)])
    p3 = Polygon([(minx, miny), (midx, miny), (midx, midy), (minx, midy)])
    p4 = Polygon([(midx, miny), (maxx, miny), (maxx, midy), (midx, midy)])
    
    sub_polys.extend([p1, p2, p3, p4])
    sub_codes.extend([f"{code}1", f"{code}2", f"{code}3", f"{code}4"])

gdf_sub = gpd.GeoDataFrame({"code": sub_codes, "geometry": sub_polys}, crs="EPSG:6675")
gdf_sub_wgs84 = gdf_sub.to_crs(epsg=4326)

print("Generated sub 4-split mesh count:", len(gdf_sub_wgs84))
print("Sample sub codes:", gdf_sub_wgs84["code"].iloc[:10].tolist())
