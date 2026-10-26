local out={}
for _,name in ipairs({"oil-refinery","chemical-plant"}) do
  local p=prototypes.entity[name]
  out[#out+1]="--- "..name
  local ok,boxes=pcall(function() return p.fluidboxes end)
  out[#out+1]="fluidboxes ok="..tostring(ok)
  if ok and boxes then
    for i,b in pairs(boxes) do
      local parts={}
      local okf,f=pcall(function() return b.filter end)
      if okf then parts[#parts+1]="filter="..tostring(f) end
      local okp,pt=pcall(function() return b.production_type end)
      if okp then parts[#parts+1]="prod="..tostring(pt) end
      local okc,pc=pcall(function() return b.pipe_connections end)
      if okc and pc then
        local cs={}
        for _,c in pairs(pc) do
          local dir="?"
          local okd,d=pcall(function() return c.direction end); if okd then dir=tostring(d) end
          local okp2,pp=pcall(function() return c.position end)
          cs[#cs+1]=tostring(pp and (pp.x..","..pp.y) or "?").." d"..dir
        end
        parts[#parts+1]="pipes="..table.concat(cs,";")
      end
      out[#out+1]="box"..i.." "..table.concat(parts,", ")
    end
  end
end
return table.concat(out,"\n")
