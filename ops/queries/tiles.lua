local s=game.surfaces.nauvis
local out={}
for _,c in ipairs({{22,66},{20,64},{-46,59},{-42,58}}) do
  out[#out+1]=string.format("center %.0f,%.0f",c[1],c[2])
  for dy=-1,1 do
    local row={}
    for dx=-1,1 do
      local x,y=c[1]+dx,c[2]+dy
      local es=s.find_entities_filtered{area={{x-0.45,y-0.45},{x+0.45,y+0.45}}}
      local n="."
      for _,e in pairs(es) do n=n..e.name.."," end
      row[#row+1]=n
    end
    out[#out+1]=table.concat(row," | ")
  end
end
return table.concat(out,"\n")
