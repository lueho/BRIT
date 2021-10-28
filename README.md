# BioResource Inventory Tool (BRIT)

BRIT was developped as the bioresource inventory module of the FLEXIBI DST.
It is used to map bioresources, create material models and run inventories
to support decision making of bioresource management. 

## The FLEXIBI project

![FLEXIBI Logo](./static/img/LOGO_Flexibi_White_BG.png)

FLEXIBI studied the potential of residues from agri– and horticulture, gardening
and landscaping, as well as from post-consumer wood from peri-urban and urban 
areas as feedstocks for Small-Scale Flexi-Feed Biorefineries (SFB). LEXIBI aims
at designing a decision support tool assessing the different pathway for the 
establishment of SFBs by evaluating all pa-rameters accounting to find
sustainable solutions.

FLEXIBI website: https://www.flexibi-biorefineries.eu

## The BIEM research group
BIEM is a research group that is dedicated to bioresource management.
It is based at the Institute of Wastewater Management 
and Water Protection of the Hamburg University of Technology. To find out more
about the group and its most recent research, visit https://www.tuhh.de/alt/aww/research/biem.

The BIEM group operates a platform to dissemminate the tools, lectures and info
material from the various projects it is involved in: https://www.bioresource-tools.net

## How to use this tool
The main instance of this tool is hosted at the Bioresource Tools platform:
https://brit.bioresource-tools.net. It is free to use and contains data and case
studies from FLEXIBI and other projects. 

If you want to run a local instance with your own database,
you can do so via Docker:

1) Clone this repository ```git clone git@github.com:lueho/BRIT.git ```
2) cd into directory ```cd flexibi_dst```
3) Build and run services ```docker-compose --profile dev up --build```

