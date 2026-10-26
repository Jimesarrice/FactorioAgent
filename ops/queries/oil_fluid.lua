local s=game.surfaces.nauvis
local t={}
for _,u in ipairs({447,445,426}) do
  for _,e in pairs(s.find_entities_filtered{area={{290,400},{370,445}}}) do
    if e.unit_number==u then
      t[#t+1]=e.name.."#"..u.." st="..tostring(e.status)
      for i=1,4 do
        local ok,f=pcall(function() return e.fluidbox[i] end)
        if ok and f then t[#t+1]="  fb"..i.."="..tostring(f.name).." "..tostring(f.amount) end
      end
    end
  end
end
return table.concat(t,"\n")
