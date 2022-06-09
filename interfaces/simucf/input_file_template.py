template_string = """Input values SimuCF

gas volumes (output) by
1000 (mbar)	norm-vol.: yes (1 bar)	0 (oC)
heap form: 	cylinder (d)
	d (m)		degradableness (%): 	carbohydrates/starch/amino acids/hemicellulose	proteins/cellulose	fats/waxs
0,400	0,400	0,694	70,000	50,000	45,000
bulk density (wet) (Mg/m³)	structure density (wet) (Mg/m³)	air temp. env. (oC)	temp. material (oC)	length of treatment
$bulk_density	0,600	20,000	20,000	$length_of_treatment
pore vol.-% (DM)	settlement (h.-%)	structure weight (wet) (kg)	structure dry solid content (weight-%)	degradable mat. weight (wet) (kg)	degr. mat. dry solid content (weight-%)
40,000	1,000	0,000	50,000	69,723	$degr_mat_dry_solid_content
heat loss (GJ/d)	water mass for temp. (kg)	temp. diff.  to mat. (oC)
0,000	30,000	3,000
isolation: yes	t = const.: no
aeration rate (m³/h)	+/- x % aeration	aer./anaerobic change at day	air pressure (bar)	aeration air: rel. humidity (RH-%)	aeration temperature (oC)	add. x (l/h) cont. to file/man.
0,000	20,000	0,000	1,000	60,000	20,000	0,000
chimney effect: no	process duration auto.: no	before/after: after	aeration file/man.: yes	without aeration: no	file/man.: aeration file
time	l/h
$aeration_rate
materials to nutrients: organic waste
carbohydrates weight (wet) (kg)	starch weight (wet) (kg)	amino acids weight (wet) (kg)	hemicellulose weight (wet) (kg)	fats weight (wet) (kg)	waxs weight (wet) (kg)	proteins weight (wet) (kg)	cellulose weight (wet) (kg)	lignin weight (wet) (kg)
$carbohydrates	$starch	$amino_acids	$hemicellulose	$fats	$waxs	$proteins	$cellulose	$lignin

add. (+) %DM of: carbohydrates weight %DM	starch weight %DM	amino acids weight %DM	hemicellulose weight %DM	fats weight %DM	waxs weight %DM	proteins weight %DM	cellulose weight %DM	lignin weight %DM	dry solid content (weight-%) of %DM
0,000	0,000	0,000	0,000	0,000	0,000	0,000	0,000	0,000	50,000
inorganics e.g. sand weight (wet) (kg)	sand dry solid cont. (weight-%)	add struct. weight (wet) (kg)	struct. dry solid cont. (weight-%)	weight of material (DM) (kg)
$inorganics	50,000	0,000	20,000	31,300
charge cont.: no
time	evap. (kg/d)
$evap
time	water input (kg/d)
$water_input
cont. evap. (kg/d):    0
cont. water input (kg/d):    0		automatic water addition: no
water input temp. (oC):  20
straw ... fish: %DM to wet of weight (DM) (kg): yes
straw weight (wet) (kg)	wood weight (wet) (kg)	barks weight (wet) (kg)	leafs weight (wet) (kg)	grass weight (wet) (kg)	fruit e.g. apples weight (wet) (kg)	potatos weight (wet) (kg)	vegetables e.g. turnips weight (wet) (kg)	grain e.g. wheat weight (wet) (kg)	pulses e.g. peas weight (wet) (kg)	flesh weight (wet) (kg)	fish weight (wet) (kg)
0,000	15,000	0,000	0,000	0,000	7,000	5,000	3,000	43,000	16,000	2,000	0,000
time	calcium carbonate dry weight (kg)
$calcium_carbonate
time	ammon. content (mg/kg oDM)
$ammonium
time	nitrate content (mg/kg oDM)
$nitrate
time	sulfate content (mg/kg oDM)
$sulfate
time	methanol (kg)
$methanol
time	ferric (III) chloride (kg)
$ferric_chloride
"""
