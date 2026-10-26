local s=game.surfaces.nauvis
local lines={}
for _,e in pairs(s.find_entities_filtered{type="mining-drill", force="player"}) do
  local ok,dp=pcall(function() return e.drop_position end)
  local ok2,ma=pcall(function() return e.mining_area end)
  lines[#lines+1]=string.format("%s#%s @(%.1f,%.1f) dir=%s drop=%s area=%s",
    e.name,tostring(e.unit_number),e.position.x,e.position.y,tostring(e.direction),
    ok and string.format("(%.1f,%.1f)",dp.x,dp.y) or "?",
    ok2 and string.format("(%.1f,%.1f)-(%.1f,%.1f)",ma.left_top.x,ma.left_top.y,ma.right_bottom.x,ma.right_bottom.y) or "?")
end
return table.concat(lines,"\n")
