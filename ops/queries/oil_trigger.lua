local t=game.forces.player.technologies["oil-processing"]
local trg=t.prototype.research_trigger
local out={}
if trg then
  for k,v in pairs(trg) do
    if type(v)=="table" then
      local parts={}; for _,x in pairs(v) do parts[#parts+1]=tostring(x) end
      out[#out+1]=k.."="..table.concat(parts,",")
    else out[#out+1]=k.."="..tostring(v) end
  end
end
return table.concat(out,"|")