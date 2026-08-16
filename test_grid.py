from japan_basic_section.grid import Grid

print("Initializing Grid for system 7, scale 2500...")
g = Grid(7, 2500)
gdf = g.make_grid()
print("Total grid features generated:", len(gdf))
print("Columns:", gdf.columns.tolist())
print(gdf.head(3))
