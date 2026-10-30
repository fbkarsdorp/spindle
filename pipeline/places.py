"""Where Thompson's traditions are, for the atlas.

Each line is: key | name | latitude | longitude | kind | other spellings.
Kinds: p, a people or place; b, a broad label for a whole region ("African",
"Polynesian"), drawn as a wash rather than a point; t, a written or religious
tradition rather than a place ("Jewish", "Italian Novella"), placed at its
historical centre and drawn as a ring.

Coordinates are approximate centres of where the tales were collected, as
the sources Thompson cites describe them (e.g. the Ekoi of the Cross River,
the Toba of the Gran Chaco), not modern borders.

    place_of("Africa (Ekoi)")  ->  "ekoi"
"""

import re
import unicodedata

TABLE = """
# ---------------------------------------------------------------- Europe
irish | Irish | 53.2 | -8.0 | p | ireland; irish myth
scottish | Scottish | 56.8 | -4.2 | p | scot; scotland; scotch; highland
english-scottish | English-Scottish border | 55.4 | -2.6 | p |
welsh | Welsh | 52.4 | -3.7 | p | wales
breton | Breton | 48.2 | -3.0 | p | brittany
manx | Manx | 54.2 | -4.5 | p | isle of man
cornish | Cornish | 50.3 | -5.0 | p |
celtic | Celtic | 53.0 | -5.5 | b | celtic (general)
celtic-norse | Celtic-Norse | 58.5 | -5.0 | b |
english | English | 52.5 | -1.5 | p | england
old english | Old English | 51.1 | -1.3 | p | middle english
english romance | English romance | 52.0 | -1.0 | t | english ballad; middle english romance; mediaeval romance; medieval romance
icelandic | Icelandic | 64.9 | -18.5 | p | iceland; modern icelandic
norse | Norse | 61.5 | 6.5 | p |
norwegian | Norwegian | 61.0 | 9.5 | p | norway
swedish | Swedish | 60.0 | 15.0 | p | sweden
danish | Danish | 56.0 | 9.5 | p | denmark
scandinavian | Scandinavian | 62.0 | 14.0 | b |
finnish | Finnish | 62.5 | 26.5 | p | finland
finnish-swedish | Finland-Swedish | 63.1 | 21.6 | p | swedish-finnish
lappish | Lappish | 68.5 | 24.5 | p | lapp; lapland; sami
estonian | Estonian | 58.7 | 25.5 | p | esthonian
livonian | Livonian | 57.6 | 22.3 | p |
latvian | Latvian | 56.9 | 25.0 | p | lettish
lithuanian | Lithuanian | 55.3 | 24.0 | p | and lithuanian
prussian | Prussian | 54.0 | 20.5 | p |
finno-ugric | Finno-Ugric | 60.0 | 40.0 | b |
german | German | 51.0 | 10.0 | p | germany
germanic | Germanic | 52.5 | 11.0 | b |
dutch | Dutch | 52.2 | 5.3 | p | holland
frisian | Frisian | 53.1 | 5.8 | p |
faroe | Faroese | 62.0 | -6.9 | p | faroe islands; faroese
flemish | Flemish | 51.0 | 3.7 | p |
swiss | Swiss | 46.8 | 8.2 | p | switzerland
austrian | Austrian | 47.5 | 14.5 | p | austria
tirol | Tirolean | 47.2 | 11.4 | p | tyrol
french | French | 46.6 | 2.5 | p | france
gascon | Gascon | 43.7 | 0.0 | p |
italian | Italian | 42.5 | 12.5 | p | italy
italian novella | Italian Novella | 43.8 | 11.25 | t | novella
sicilian | Sicilian | 37.5 | 14.0 | p | sicily
spanish | Spanish | 40.0 | -3.7 | p | spain
spanish exempla | Spanish Exempla | 39.9 | -4.0 | t |
portuguese | Portuguese | 39.5 | -8.0 | p | portugal
catalan | Catalan | 41.8 | 1.5 | p |
basque | Basque | 43.0 | -2.5 | p |
russian | Russian | 56.0 | 38.0 | p | russia
slavic | Slavic | 51.5 | 28.0 | b | slavic (general); slav
slavic (elbe) | Elbe Slavs | 52.5 | 12.5 | p |
czech | Czech | 49.8 | 15.5 | p | bohemian; bohemia
polish | Polish | 52.0 | 19.5 | p | poland
wendish | Wendish | 51.5 | 14.3 | p |
hungarian | Hungarian | 47.2 | 19.5 | p | hungary; magyar
romanian | Romanian | 45.9 | 25.0 | p | rumanian
bulgarian | Bulgarian | 42.7 | 25.3 | p |
serbian | Serbian | 44.0 | 20.8 | p | serb; jugo-slav; yugoslav; serbo-croatian
cheremis | Cheremis | 56.6 | 47.9 | p |
mordvin | Mordvin | 54.2 | 44.5 | p |
votyak | Votyak | 57.0 | 53.0 | p |
caucasian | Caucasian | 43.0 | 44.0 | b |
circassian | Circassian | 44.2 | 40.5 | p |
georgian | Georgian | 42.0 | 43.5 | p |
armenian | Armenian | 40.2 | 44.5 | p |
gypsy | Gypsy | 47.0 | 22.0 | t |

# ------------------------------------------- Mediterranean & Near East
greek | Greek | 38.5 | 22.5 | p | greece; modern greek; greek fable; greek myth; greek (herodotus); greek-roman; greek-latin
roman | Roman | 41.9 | 12.5 | p | roman myth; rome
latin | Latin | 41.4 | 13.6 | t |
etruscan | Etruscan | 42.6 | 11.8 | p |
cyprus | Cyprus | 35.0 | 33.2 | p | cypriote
turkish | Turkish | 39.0 | 35.0 | p | turkey; turk
persian | Persian | 32.5 | 53.5 | p | persia; iran; iranian; chinese-persian; indo-iranian
arabian | Arabian | 24.0 | 45.0 | p | arab; arabic; arabia
mohammedan | Islamic | 21.4 | 39.8 | t | islamic; moslem
jewish | Jewish | 31.8 | 35.2 | t | hebrew; talmud; rabbinic
palestine | Palestine | 32.5 | 35.0 | p |
semitic | Semitic | 31.0 | 40.0 | b |
western asia | Western Asia | 35.0 | 42.0 | b | western asia (general)
babylonian | Babylonian | 32.5 | 44.4 | p | babylonia; sumerian
assyrian | Assyrian | 36.4 | 43.2 | p |
hittite | Hittite | 40.0 | 34.6 | p |
egyptian | Egyptian | 26.5 | 31.5 | p | egypt

# ------------------------------------------------------------ South Asia
india | India | 22.5 | 79.0 | p | indian; east indian; india (general)
hindu | Hindu | 25.3 | 83.0 | t | indian (hindu)
buddhist | Buddhist | 24.7 | 85.0 | t | buddhist myth; buddhist. myth
tibetan | Tibetan | 31.0 | 88.0 | p | tibet
ceylon | Ceylon | 7.8 | 80.7 | p | sinhalese
andaman | Andaman Islands | 12.0 | 92.8 | p | andaman is; andaman islands
santal | Santal | 24.0 | 87.0 | p |

# ------------------------------------------------------------- East Asia
chinese | Chinese | 34.0 | 110.0 | p | china
japanese | Japanese | 36.5 | 138.0 | p | japan
ainu | Ainu | 43.5 | 143.0 | p |
korean | Korean | 36.5 | 127.8 | p | korea
formosa | Formosa | 23.7 | 121.0 | p | taiwan
indo-chinese | Indo-Chinese | 16.0 | 104.0 | b | indo-china; indochinese
burmese | Burmese | 21.0 | 96.0 | p | burma
kachin | Kachin | 25.5 | 97.4 | p | kachin (north burma)
chin | Chin | 22.5 | 93.6 | p | chin (indo-china)
wa | Wa | 22.5 | 99.3 | p | wa (indo-chinese); wa (indo-china)
siamese | Siamese | 15.0 | 101.0 | p | thai; siam
annamese | Annamese | 16.0 | 107.5 | p | annam
mongolian | Mongolian | 47.0 | 104.0 | p | mongol

# ----------------------------------------------- Siberia & Central Asia
siberian | Siberian | 62.0 | 100.0 | b | siberia
buriat | Buriat | 52.5 | 108.0 | p |
koryak | Koryak | 61.0 | 163.0 | p | eskimo (koryak)
chukchi | Chukchi | 66.0 | 175.0 | p | chukchee; chuckchee
yakut | Yakut | 63.0 | 130.0 | p | yakuts
tungus | Tungus | 61.0 | 105.0 | p |
kirghis | Kirghiz | 41.5 | 75.0 | p | kirghiz
kalmuck | Kalmyk | 46.5 | 45.3 | p | kalmyk; kalmuk
tatar | Tatar | 55.8 | 49.1 | p | tartar
samoyed | Samoyed | 67.0 | 70.0 | p |
ostyak | Ostyak | 61.0 | 69.0 | p |
vogul | Vogul | 61.5 | 62.0 | p |
altai | Altai | 50.5 | 86.5 | p |

# ----------------------------------------------------------- Oceania
oceania | Oceanic | -10.0 | 172.0 | b | oceanic; oceanian
polynesian | Polynesian | -15.0 | -150.0 | b | polynesia
western polynesia | Western Polynesia | -15.0 | -175.0 | b |
melanesian | Melanesian | -10.0 | 158.0 | b | melanesia
micronesian | Micronesian | 8.0 | 155.0 | b | micronesia
hawaiian | Hawaiian | 20.5 | -157.0 | p | hawaii; oahu (hawaii); oahu
tahiti | Tahitian | -17.65 | -149.4 | p | tahitian
tuamotu | Tuamotu | -17.0 | -143.0 | p |
marquesas | Marquesas | -9.0 | -139.8 | p | marquesas is; hivaoa (marquesas); nukuhiva (marquesas)
easter island | Easter Island | -27.1 | -109.35 | p | easter is
cook islands | Cook Islands | -21.2 | -159.8 | p | cook is; cook island; cook group; rarotonga; raratonga; rarotonga (cook island); raratonga (cook island)
mangaia | Mangaia | -21.9 | -157.9 | p | mangaia (cook is.); mangaia (cook island); mangia (cook is.)
tonga | Tongan | -21.2 | -175.2 | p | tongan
samoa | Samoan | -13.8 | -172.0 | p | samoan
fiji | Fijian | -17.8 | 178.0 | p | fijis; fijian
chatham is | Chatham Islands | -44.0 | -176.5 | p | chatham islands; chatham island
maori | Maori | -39.0 | 175.5 | p | new zealand; new zealand (maori)
new hebrides | New Hebrides | -16.0 | 167.0 | p | new hebrides (banks is.)
banks is | Banks Islands | -14.0 | 167.5 | p | banks island; banks is. (fiji)
lepers island | Lepers Island | -15.4 | 167.85 | p | lepers is
solomon is | Solomon Islands | -9.5 | 160.0 | p | solomon islands
mono-alu | Mono-Alu | -7.4 | 155.6 | p | mono; alu; mono alu; mono-alu-fauru; mono-alu (fauru)
buin | Buin | -6.75 | 155.7 | p |
ysabel | Ysabel | -8.0 | 159.2 | p | melanesia (ysabel)
new britain | New Britain | -5.3 | 151.5 | p | sulka of new britain; sulka (new britain); baining of new britain
admiralty is | Admiralty Islands | -2.1 | 147.0 | p | admiralty islands
new guinea | New Guinea | -5.5 | 142.0 | p |
papua | Papuan | -8.0 | 146.0 | p | papuan; british new guinea; papuan (british new guinea)
massim | Massim | -10.3 | 150.5 | p | massim of british new guinea; massim (british new guinea)
german new guinea | German New Guinea | -5.5 | 145.5 | p | oceanic (german new guinea
kai | Kai | -6.6 | 147.4 | p | kai (german new guinea); kai of new guinea
torres straits | Torres Straits | -10.0 | 142.5 | p |
marshall is | Marshall Islands | 7.1 | 171.2 | p | marshall islands
gilbert is | Gilbert Islands | 1.4 | 173.0 | p | gilbert is. (micronesia)
pleasant island | Nauru | -0.5 | 166.9 | p | pleasant island (micronesia)
pelew is | Palau | 7.5 | 134.6 | p | pelew is. (micronesia)
west caroline is | West Caroline Islands | 9.5 | 138.1 | p |
caroline islands | Caroline Islands | 7.0 | 150.0 | p | caroline is
central caroline is | Central Caroline Islands | 7.4 | 151.8 | p | central caroline islands
indonesian | Indonesian | -2.0 | 118.0 | b | indonesia
eastern indonesian | Eastern Indonesian | -7.0 | 125.0 | b | eastern indonesia
borneo | Borneo | 1.0 | 114.0 | p |
sumatra | Sumatra | 0.0 | 101.5 | p | sumatran
java | Java | -7.3 | 110.0 | p | javanese
batak | Batak | 2.3 | 99.0 | p |
nias | Nias | 1.1 | 97.6 | p | nias is; nias is. (indonesia)
kei is | Kei Islands | -5.6 | 132.7 | p | kei is. (indonesia)
celebes | Celebes | -2.0 | 121.0 | p |
minahassa | Minahassa | 1.3 | 124.8 | p | minahassa (celebes)
malay | Malay | 4.0 | 102.0 | p | malaya; malay peninsula
philippine | Philippine | 13.0 | 122.0 | p | philippines; filipino
tinguian | Tinguian | 17.5 | 120.7 | p | philippine (tinguian)
madagascar | Madagascar | -19.0 | 46.7 | p | malagasy; madagascar (imerina); madagascar (antankarana); africa (madagascar); betsileo
australian | Australian | -25.0 | 134.0 | b | australia
northern australia | Northern Australia | -14.0 | 133.0 | p |

# ------------------------------------------------------------ Africa
africa | African | 5.0 | 20.0 | b | african
west africa | West Africa | 10.0 | -5.0 | b | western sudan
east africa | East Africa | -2.0 | 36.0 | b |
south africa | South Africa | -29.0 | 25.0 | b | south african; southeastern africa
bantu | Bantu | -5.0 | 25.0 | b |
sudanese | Sudanese | 12.0 | 15.0 | b | sudan
ekoi | Ekoi | 5.8 | 8.8 | p |
fang | Fang | 1.5 | 11.0 | p | pangwe; pahouin; pahouini; pahouine
basuto | Basuto | -29.5 | 28.0 | p | suto; sotho
kaffir | Xhosa ("Kaffir") | -32.5 | 27.5 | p | xhosa
zulu | Zulu | -28.5 | 31.0 | p |
swazi | Swazi | -26.5 | 31.5 | p |
angola | Angola (Mbundu) | -9.5 | 15.5 | p | mbundu; bangola
cameroon | Cameroon | 5.5 | 12.0 | p | cameroons; kamerun
benga | Benga | 1.0 | 9.6 | p |
fjort | Fjort (Loango coast) | -5.0 | 12.3 | p |
loango | Loango | -4.3 | 11.8 | p |
gold coast | Gold Coast | 6.0 | -1.2 | p | tshi; cold coast
ashanti | Ashanti | 6.7 | -1.6 | p | akan-ashanti
congo | Congo | -4.5 | 15.0 | p |
boloki | Boloki | 1.6 | 19.0 | p |
wakweli | Bakweri | 4.2 | 9.3 | p | kweli
duala | Duala | 4.05 | 9.7 | p |
luba | Luba | -7.5 | 25.0 | p | baluba; baluga
hottentot | Hottentot | -26.5 | 17.5 | p | nama
bushman | Bushman | -22.0 | 21.5 | p | bushman (south of zambesi); bushmen
vai | Vai | 7.0 | -11.2 | p |
liberia | Liberian | 6.5 | -9.5 | p | liberian
kpelle | Kpelle | 7.2 | -9.7 | p |
temne | Temne | 8.9 | -12.5 | p |
konnoh | Kono | 8.6 | -11.0 | p | kono
upoto | Upoto | 2.1 | 21.5 | p |
mpongwe | Mpongwe | 0.4 | 9.45 | p |
ila | Ila | -15.8 | 26.5 | p | ila (rhodesia); ila of rhodesia
tonga (africa) | Tonga (Zambezi) | -16.3 | 27.5 | p | africa (tonga)
lamba | Lamba | -13.0 | 28.0 | p |
rozwi | Rozwi | -20.0 | 30.5 | p |
venda | Venda | -22.8 | 30.5 | p |
hausa | Hausa | 12.0 | 8.5 | p |
yoruba | Yoruba | 7.5 | 4.0 | p | nago
ibo | Igbo | 5.8 | 7.3 | p | ibo (nigeria); ibo of nigeria
nigeria | Nigeria | 9.0 | 8.0 | p |
dahome | Dahomey | 7.2 | 2.1 | p | dahomey; dahomé
togo | Togo (Ewe) | 7.5 | 1.0 | p | ewe
mossi | Mossi | 12.4 | -1.5 | p |
bambara | Bambara | 13.0 | -7.5 | p |
fulah | Fula | 11.5 | -12.0 | p | fula; fulani
senegambia | Senegambia | 13.5 | -15.5 | p |
cape verde islands | Cape Verde Islands | 15.1 | -23.6 | p | cape verde; cape verde is
swahili | Swahili | -6.0 | 39.2 | p | zanzibar
dzalamo | Zaramo | -6.9 | 39.2 | p | zaramo
bondei | Bondei | -5.2 | 38.7 | p | tanga
wachaga | Chaga | -3.2 | 37.4 | p | chaga; washaga; dschagga
masai | Maasai | -2.5 | 36.5 | p | maasai
larusa | Arusha | -3.4 | 36.7 | p |
ganda | Ganda | 0.3 | 32.6 | p | baganda; uganda
ziba | Haya (Ziba) | -1.3 | 31.8 | p |
konde | Nyakyusa (Konde) | -9.3 | 33.8 | p |
mkulwe | Mkulwe | -8.5 | 31.8 | p |
baholoholo | Holoholo | -6.0 | 29.5 | p |
nyanja | Nyanja | -14.0 | 34.5 | p |
thonga | Thonga | -24.5 | 33.0 | p | shangani; shangaan; shangang
ba ronga | Ronga | -25.9 | 32.6 | p | ronga; baronga
bushongo | Kuba (Bushongo) | -4.5 | 21.5 | p | bushonga; bakuba; bushango
kordofan | Kordofan | 13.0 | 30.0 | p | nuba
nubian | Nubian | 19.5 | 32.5 | p | nubia
dinka | Dinka | 7.5 | 29.5 | p |
sandeh | Zande | 4.5 | 27.5 | p | zande; azande
somali | Somali | 6.0 | 46.0 | p |
wute | Vute | 5.8 | 12.0 | p | weute; vute
bankon | Abo (Bankon) | 4.3 | 10.0 | p |
bulu | Bulu | 2.9 | 11.2 | p |
jaunde | Yaunde | 3.9 | 11.5 | p | yaunde
nyang | Banyang | 5.6 | 9.5 | p |
herero | Herero | -21.5 | 17.0 | p |
lamomi | Lamomi | 2.0 | 21.0 | p |
tswana | Tswana | -24.5 | 25.0 | p | bechuana
efik | Efik | 4.95 | 8.3 | p | efik-ibibo
nupe | Nupe | 9.1 | 6.0 | p |
rundi | Rundi | -3.4 | 29.9 | p |
kenya | Kenya | 0.0 | 37.9 | p |
mambettu | Mangbetu | 3.0 | 27.5 | p | mangbetu
bayaka | Yaka | -6.0 | 17.0 | p |
ndau | Ndau | -20.0 | 33.5 | p |
zezuru | Zezuru | -17.8 | 31.0 | p |
guinea coast | Guinea Coast | 5.5 | -3.0 | b |
north africa | North Africa | 31.0 | 3.0 | b | berber; algerian

# ---------------------------------------------------------- the Arctic
eskimo | Eskimo | 67.0 | -100.0 | b | inuit
eskimo (greenland) | Greenland | 64.2 | -51.7 | p | greenland; eskimo (west greenland)
eskimo (east greenland) | East Greenland | 65.6 | -37.6 | p | eskimo (e. greenland)
eskimo (smith sound) | Polar Eskimo | 77.5 | -70.0 | p | eskimo (cape york)
eskimo (mackenzie area) | Mackenzie | 69.0 | -134.0 | p |
eskimo (cumberland sound) | Cumberland Sound | 65.5 | -66.5 | p |
eskimo (bering strait) | Bering Strait | 64.5 | -165.0 | p |
eskimo (kodiak) | Kodiak | 57.6 | -153.5 | p |
eskimo (west hudson bay) | West Hudson Bay | 62.5 | -93.0 | p | eskimo (w. hudson bay)
eskimo (labrador) | Labrador | 56.5 | -61.5 | p |
eskimo (ungava) | Ungava | 59.5 | -69.0 | p |
eskimo (central) | Central Eskimo | 67.5 | -82.0 | p | eskimo (central eskimo)
eskimo (alaska) | Alaska | 64.0 | -152.0 | p | alaska
aleut | Aleut | 53.5 | -167.0 | p | eskimo (aleut)

# --------------------------------------------------- North America
north american indian | North American Indian | 45.0 | -100.0 | b | american indian; north american indian (general)
california | California | 37.5 | -120.5 | p | north american indian (california); california indian; north american indian (calif.); california indians
plains | Plains | 43.0 | -102.0 | b | plains in general; north american indian (plains tribes)
central algonquin | Central Algonquian | 45.0 | -86.0 | b |
tahltan | Tahltan | 58.0 | -131.0 | p |
kaska | Kaska | 60.0 | -128.0 | p |
seneca | Seneca | 42.8 | -77.5 | p |
iroquois | Iroquois | 43.0 | -75.5 | p |
wyandot | Wyandot | 41.8 | -83.0 | p |
zuni | Zuñi | 35.07 | -108.85 | p | zuñi
hopi | Hopi | 35.8 | -110.5 | p |
pueblo | Pueblo | 35.5 | -106.5 | p |
sia | Zia | 35.5 | -106.73 | p | zia
laguna | Laguna | 35.04 | -107.4 | p |
navaho | Navaho | 36.2 | -109.5 | p | navajo
apache | Apache | 33.5 | -109.5 | p | san carlos apache; white mountain apache
jicarilla apache | Jicarilla Apache | 36.5 | -105.5 | p |
pima | Pima | 33.0 | -111.8 | p |
klikitat | Klikitat | 46.0 | -121.0 | p |
thompson river | Thompson River | 50.4 | -121.4 | p | n’tlaka’panaq; thompson
lillooet | Lillooet | 50.7 | -121.9 | p |
salishan | Salish | 48.5 | -122.0 | b | salish
quileute | Quileute | 47.9 | -124.6 | p |
kathlamet | Kathlamet | 46.2 | -123.4 | p |
alsea | Alsea | 44.4 | -124.0 | p |
joshua | Joshua (Tututni) | 42.4 | -124.2 | p |
nootka | Nootka | 49.6 | -126.6 | p |
bella bella | Bella Bella | 52.2 | -128.1 | p | bella-bella
tsimshian | Tsimshian | 54.3 | -130.0 | p |
haida | Haida | 53.5 | -132.0 | p |
tlingit | Tlingit | 58.3 | -134.4 | p |
carrier | Carrier | 54.0 | -124.5 | p |
dene | Déné | 61.0 | -115.0 | p | déné; chippewyan
yukon | Yukon | 63.0 | -136.0 | p |
shasta | Shasta | 41.5 | -122.5 | p |
karok | Karok | 41.5 | -123.5 | p |
hupa | Hupa | 41.05 | -123.7 | p |
yana | Yana | 40.5 | -122.0 | p |
maidu | Maidu | 39.5 | -121.0 | p |
miwok | Miwok | 38.0 | -120.3 | p |
western mono | Western Mono | 37.0 | -119.3 | p | north american indian (mono)
salinan | Salinan | 35.9 | -121.0 | p |
mohave | Mohave | 34.9 | -114.6 | p |
paiute | Paiute | 39.5 | -118.0 | p | northern paiute; southern paiute
southern ute | Southern Ute | 37.1 | -107.6 | p |
blackfoot | Blackfoot | 48.5 | -112.5 | p |
crow | Crow | 45.6 | -107.5 | p |
cheyenne | Cheyenne | 45.5 | -106.5 | p |
arapaho | Arapaho | 41.0 | -105.0 | p |
teton | Teton | 44.0 | -101.5 | p |
dakota | Dakota | 44.5 | -97.0 | p | canadian dakota; sioux
assiniboin | Assiniboine | 50.5 | -105.0 | p |
plains cree | Plains Cree | 52.5 | -107.0 | p |
plains ojibwa | Plains Ojibwa | 50.0 | -98.0 | p |
mandan | Mandan | 47.3 | -101.4 | p |
arikara | Arikara | 45.5 | -100.4 | p |
pawnee | Pawnee | 41.5 | -98.5 | p |
omaha | Omaha | 42.0 | -96.5 | p |
kiowa | Kiowa | 35.0 | -98.5 | p |
ojibwa | Ojibwa | 47.0 | -89.0 | p | chippewa
menomini | Menomini | 45.0 | -88.5 | p | montagnais and menominee
winnebago | Winnebago | 43.8 | -89.5 | p |
fox | Fox | 41.6 | -91.5 | p |
montagnais | Montagnais | 50.5 | -68.0 | p |
naskapi | Naskapi | 54.5 | -67.0 | p |
micmac | Micmac | 46.0 | -63.0 | p |
malecite | Maliseet | 46.0 | -67.5 | p | maliseet
passamaquoddy | Passamaquoddy | 45.0 | -67.2 | p |
penobscot | Penobscot | 45.0 | -68.8 | p |
mohegan | Mohegan | 41.4 | -72.1 | p |
wampanoag | Wampanoag | 41.7 | -70.6 | p |
cherokee | Cherokee | 35.5 | -83.5 | p |
creek | Creek | 32.5 | -85.5 | p |
choctaw | Choctaw | 32.5 | -89.0 | p |
biloxi | Biloxi | 30.4 | -89.0 | p |
bella coola | Bella Coola | 52.4 | -126.8 | p |
kwakiutl | Kwakiutl | 50.6 | -127.0 | p |
okanagon | Okanagan | 49.0 | -119.5 | p |
shuswap | Shuswap | 50.9 | -119.5 | p |
chilcotin | Chilcotin | 52.0 | -123.5 | p |
quinault | Quinault | 47.4 | -124.0 | p |
twana | Twana | 47.4 | -123.1 | p |
snohomish | Snohomish | 48.0 | -122.2 | p |
wasco | Wasco | 45.6 | -121.2 | p |
takelma | Takelma | 42.5 | -123.3 | p |
luiseno | Luiseño | 33.4 | -117.2 | p | luiseño
shoshoni | Shoshoni | 43.0 | -113.0 | p | shoshonean
kutenai | Kutenai | 49.5 | -116.0 | p |
flathead | Flathead | 47.5 | -114.0 | p |
atsina | Atsina | 48.5 | -108.5 | p |
ponca | Ponca | 42.8 | -98.0 | p | ponka
wichita | Wichita | 34.0 | -98.0 | p |
chickasaw | Chickasaw | 34.5 | -88.5 | p |
catawba | Catawba | 34.9 | -80.9 | p |
peoria | Peoria | 40.7 | -89.6 | p |

# ----------------------------------- Afro-Caribbean & North American folk
united states | United States | 38.5 | -94.0 | p | u.s; u.s.a; us; england-u.s; u.s. (lumbermen)
african american | African American | 32.5 | -86.5 | b | negro; american negro; u.s. negro
georgia | Georgia | 32.7 | -83.4 | p | african american (georgia); georgia negro
virginia | Virginia | 37.5 | -78.5 | p | virginian; african american (virginia); virginia (negro); madison county virginia (u.s.a.)
north carolina | North Carolina | 35.5 | -79.5 | p | n. carolina; u.s. (n. carolina); african american (north carolina); north carolina negro; n. carolina negro
south carolina | South Carolina | 33.8 | -80.9 | p | u.s. (s. carolina); s. carolina negro
pennsylvania | Pennsylvania | 40.9 | -77.8 | p | african american (pennsylvania)
new york | New York | 42.9 | -75.5 | p | u.s. (new york state)
ozarks | Ozarks | 36.5 | -92.5 | p | u.s. (ozarks)
texas | Texas | 31.0 | -99.0 | p |
new mexican spanish | New Mexican Spanish | 35.7 | -106.0 | p | new mexican; new mexico
louisiana creole | Louisiana Creole | 30.5 | -91.5 | p | louisiana; louisiana french
missouri french | Missouri French | 37.9 | -90.7 | p |
french canadian | French Canadian | 46.8 | -71.2 | p |
canada | Canada | 52.0 | -85.0 | p | canadian
west indies | West Indies | 17.0 | -66.0 | b | british west indies; antilles; caribbean
jamaica | Jamaica | 18.1 | -77.3 | p | jamaica negro; jamaican
bahama | Bahamas | 24.5 | -77.5 | p | bahamas
haiti | Haiti | 19.0 | -72.5 | p | haitian
surinam | Surinam | 4.0 | -56.0 | p |

# ---------------------------------------------------- Latin America
south american indian | South American Indian | -12.0 | -60.0 | b | south american indians; latin american; south american indian (tropical forest); south american indian (amazon tribes)
central america | Central American | 14.0 | -87.0 | b | central american
mexican | Mexican | 21.0 | -101.5 | p | mexico; mexican indian; mexican spanish
aztec | Aztec | 19.43 | -99.13 | p | tepoztlan
maya | Maya | 19.5 | -89.0 | p |
quiche | Quiché | 15.0 | -91.2 | p | quiché
tarascan | Tarascan | 19.6 | -101.6 | p |
tarahumare | Tarahumara | 27.5 | -107.0 | p | tarahumare (mexican indian); tarahumare and tepehuane
cora | Cora | 22.0 | -104.9 | p |
cahita | Cahita | 27.5 | -109.5 | p |
pochulata | Pochutla | 15.7 | -96.5 | p |
isthmian tribes | Isthmian tribes | 8.5 | -80.0 | p | isthmian tribes (panama)
nicaragua | Nicaragua | 12.8 | -85.0 | p |
honduras | Honduras | 14.8 | -86.8 | p | ladino (honduras
guatemala | Guatemala | 15.5 | -90.3 | p | chuh (indians of guatemala); chuh
puerto rico | Puerto Rico | 18.2 | -66.5 | p |
cuba | Cuba | 21.5 | -79.5 | p | caribbean (cuan)
carib | Carib | 5.0 | -57.0 | p | karib; tamanac (carib)
guiana | Guiana | 5.5 | -58.5 | p | guianas
venezuela | Venezuela | 8.0 | -66.0 | p |
warrau | Warrau | 9.0 | -61.5 | p | warrau (carib); warrau (carib tribe)
ackawoi | Akawaio | 6.0 | -60.5 | p | ackawoi (orinoco)
chibcha | Chibcha | 5.0 | -73.5 | p | tunja (colombia); muzo (colombia); pijaos (colombia); chibcha (with reference to other south american tribes); tunja
antioquians | Antioquia | 6.5 | -75.6 | p |
cubeo | Cubeo | 1.0 | -70.5 | p | cubao
witoto | Witoto | -1.0 | -73.0 | p |
yagua | Yagua | -3.5 | -72.5 | p |
tucuna | Tucuna | -3.8 | -69.5 | p |
jivaro | Jívaro | -3.0 | -78.0 | p | jibaro; jíbaros; jivaró
amazon | Amazon | -3.0 | -60.0 | b |
ipurina | Ipurinã | -8.0 | -67.0 | p |
cashinawa | Cashinawa | -9.5 | -71.0 | p |
inca | Inca | -13.5 | -72.0 | p | viracocha; huarochiri
chincha | Chincha | -13.4 | -76.1 | p | chincha (peru)
yunca | Yunca | -7.5 | -79.5 | p | yunca (peru)
huamachuco | Huamachuco | -7.8 | -78.0 | p |
amuesha | Amuesha | -10.5 | -75.3 | p | amuesa
aymara | Aymara | -16.5 | -68.5 | p | amyra; amyara
uru-chipaya | Uru-Chipaya | -19.0 | -68.0 | p |
yuracare | Yuracare | -16.5 | -65.5 | p | yurakare; yurakari; yuracari; yuracare (west brazil); yuricare
mojo | Mojo | -15.0 | -65.0 | p |
more | Moré | -12.5 | -64.5 | p | moré
cavina | Cavineña | -13.0 | -67.5 | p | caviña
tiatinagua | Tiatinagua | -12.5 | -69.5 | p |
guapore | Guaporé | -12.5 | -63.0 | p | guaporé river; guapore river
guarayu | Guarayú | -15.5 | -63.0 | p | guarayú
chiriguano | Chiriguano | -20.0 | -63.5 | p |
toba | Toba | -24.5 | -60.0 | p |
mataco | Mataco | -22.5 | -63.0 | p | matoco; metaco
choroti | Chorotí | -22.5 | -62.0 | p | chorotí
ashlushlay | Ashlushlay | -22.3 | -61.5 | p |
chaco | Gran Chaco | -23.0 | -61.0 | p | south american indian (chaco); pilcomayo river tribes
lengua | Lengua | -23.0 | -59.0 | p |
chamacoco | Chamacoco | -20.0 | -58.3 | p | camacoco
mbaya | Mbayá | -20.5 | -57.5 | p | mbayá
mocovi | Mocoví | -28.5 | -60.5 | p | mocoví; macovi
terino | Terena | -20.5 | -56.0 | p | terena; tereno
paressi | Paressi | -13.5 | -58.0 | p |
bororo | Bororo | -16.0 | -55.0 | p |
bacairi | Bakairi | -13.5 | -55.0 | p | bakairi; baikairi; bakuiri
central brazil | Central Brazil | -12.5 | -52.0 | p | indians of central brazil
caraja | Carajá | -11.0 | -50.5 | p | carajá
tapirape | Tapirapé | -10.7 | -50.7 | p | tapirapé
sherente | Sherente | -9.0 | -48.0 | p | cherentes; charentes; sherenti
tembe | Tembé | -2.5 | -47.0 | p | tembé; tenetehara; tenibe
mundurucu | Mundurucú | -6.5 | -57.0 | p | munderucú; mundurucú
arua | Arua | -11.0 | -61.5 | p |
cariri | Cariri | -7.5 | -39.5 | p | kariri
botocudo | Botocudo | -19.0 | -41.5 | p |
camacan | Camacan | -15.0 | -39.5 | p |
tupinamba | Tupinamba | -13.0 | -38.8 | p | tupenamba
tupi | Tupi | -15.0 | -45.0 | b |
eastern brazil | Eastern Brazil | -12.0 | -41.0 | p |
brazil | Brazil | -10.0 | -52.0 | b |
guarani | Guarani | -25.5 | -56.0 | p | guaraní
apapocuva-guarani | Apapocuvá-Guarani | -22.5 | -55.5 | p | apapocuvá-guarani; apapocuvá-guaraní; apapocuvú-guarani; apapocuvú-guaraní; apapocuva-guarani; apapocuvu-guaraní
kaigua | Kaiguá | -22.5 | -55.0 | p | kaiguá
guayaki | Guayakí | -26.0 | -55.5 | p |
caingang | Kaingang | -26.0 | -52.0 | p | kaingang; kaigang; caingeng
argentina | Argentina | -34.0 | -64.0 | p |
paraguay | Paraguay | -23.4 | -58.4 | p |
peru | Peru | -10.0 | -75.5 | p |
colombia | Colombia | 4.5 | -74.0 | p | south america (colombia
araucanian | Araucanian | -38.5 | -72.5 | p |
chile | Chile | -33.5 | -71.0 | p |
tehuelche | Tehuelche | -45.0 | -69.0 | p |
oaxaca | Oaxaca | 17.0 | -96.7 | p | tuxtapec
arawak | Arawak | 5.8 | -55.5 | p | arawak of surinam
apinaye | Apinayé | -6.0 | -48.0 | p | aspinayé; apinayé
mura | Mura | -5.0 | -61.0 | p |
fuegian | Fuegian | -54.5 | -69.0 | p | fueginos; gusinde
"""

KIND_NAMES = {"p": "place", "b": "broad", "t": "tradition"}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = s.replace("’", "'")
    return re.sub(r"\s+", " ", s).strip(" .,;:*")


def load():
    places, alias = {}, {}
    for line in TABLE.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, name, lat, lon, kind, also = [x.strip() for x in line.split("|")]
        assert key not in places, key
        places[key] = {"key": key, "name": name, "lat": float(lat), "lon": float(lon), "kind": kind}
        for a in [key, name] + [x for x in also.split(";") if x.strip()]:
            a = norm(a)
            assert alias.get(a, key) == key, f"{a} is both {alias[a]} and {key}"
            alias[a] = key
    return places, alias


PLACES, ALIAS = load()

# the region-wide label to fall back on for an unknown people in a group
GROUPS = {"africa": "africa", "african": "africa", "north american indian": "north american indian",
          "n. american indian": "north american indian", "american indian": "north american indian",
          "south american indian": "south american indian", "s. am. indian": "south american indian",
          "s. am. indians": "south american indian", "eskimo": "eskimo", "african american": "african american",
          "oceanic": "oceania", "melanesia": "melanesian", "philippine": "philippine", "papua": "papua",
          "india": "india", "u.s": "united states", "madagascar": "madagascar"}


def place_of(label: str):
    """The key of the place a tradition label belongs to, or None."""
    s = norm(label)
    # stray text before a closing bracket: "etc.) Italian Novella"
    if ")" in s and "(" not in s.split(")")[0]:
        head, _, tail = s.partition(")")
        tail = tail.strip()
        s = tail if tail and not tail.startswith("(") else head.strip()
    if s in ALIAS:
        return ALIAS[s]
    m = re.match(r"^(.*?)\s*\((.*?)\)?(?:\s*\(.*)?$", s)
    if m:
        group, people = m.group(1).strip(), m.group(2).strip()
        people = re.sub(r"\s*\[.*$", "", people)
        for cand in (f"{group} ({people})", people, people.split(",")[0].strip(), group):
            if cand in ALIAS:
                return ALIAS[cand]
        if group in GROUPS:
            return GROUPS[group]
    if " of " in s:
        a, _, b = s.partition(" of ")
        for cand in (a, b):
            if cand in ALIAS:
                return ALIAS[cand]
    return None
