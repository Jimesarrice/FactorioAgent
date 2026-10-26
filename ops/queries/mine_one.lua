local s=game.surfaces.nauvis
local p=game.players["LLM-Bot"]
local out={}
local r=s.find_entities_filtered{position={x=-63.5,y=48.5},radius=0.2,type="resource"}
out[#out+1]="found="..#r
for _,e in ipairs(r) do
  local ok,res=pcall(function() return p.mine_entity(e,false) end)
  out[#out+1]="mine ok="..tostring(ok).." res="..tostring(res).." valid="..tostring(e.valid)
end
out[#out+1]="pos="..p.physical_position.x..","..p.physical_position.y
return table.concat(out,"\n")
