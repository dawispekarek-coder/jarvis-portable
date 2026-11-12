from pathlib import Path
p=Path(r'H:\RealJarvis\OptionalPlugins\JarvisGodot2D\LaliPooli2D_Pilot\training\homecoming\Stage4_Homecoming.gd')
s=p.read_text(encoding='utf8')
backup=p.with_suffix('.gd.before_hug_quality_20261028.bak')
if not backup.exists():backup.write_bytes(p.read_bytes())
if 'LeftArmPivot' not in s:
 anchor=' root.add_child(sprite_part(who,"body"))'
 assert anchor in s
 s=s.replace(anchor,anchor+"""
 var left_pivot=Node2D.new()
 left_pivot.name="LeftArmPivot"
 left_pivot.position=Vector2(74,154)
 root.add_child(left_pivot)
 var left_arm=sprite_part(who,"arm")
 left_arm.flip_h=true
 left_arm.position=-left_pivot.position
 left_pivot.add_child(left_arm)""",1)
 s=s.replace('105+300*run','105+235*run')
 s=s.replace('850-270*enter-60*hug','850-270*enter-75*hug')
 s=s.replace('lali.get_node("ArmPivot").rotation=deg_to_rad(-13.0*notice+18.0*sin(x*13.0)*run*(1.0-hug)-29.0*hug)',
 'lali.get_node("ArmPivot").rotation=deg_to_rad(-13.0*notice+18.0*sin(x*13.0)*run*(1.0-hug)-55.0*hug)\n lali.get_node("LeftArmPivot").rotation=deg_to_rad(40.0*hug)')
 s=s.replace('pooli.get_node("ArmPivot").rotation=deg_to_rad(15.0*enter+17.0*sin(x*9.0)*enter*(1.0-hug)+35.0*hug)',
 'pooli.get_node("ArmPivot").rotation=deg_to_rad(15.0*enter+17.0*sin(x*9.0)*enter*(1.0-hug)+50.0*hug)\n pooli.get_node("LeftArmPivot").rotation=deg_to_rad(-48.0*hug)')
 s=s.replace('lali.scale=Vector2(2.15+0.06*leap,2.15-0.07*leap)',
 'lali.scale=Vector2(2.15+0.06*leap,2.15-0.07*leap)\n lali.z_index=2 if x>9.9 else 0')
 p.write_text(s,encoding='utf8')
 print('HUG_RIG_UPDATED',len(s))
