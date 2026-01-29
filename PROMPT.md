Make a tool to take music from archive.org and upload it to youtube. 

The tool should take as input a URL like this one:

https://archive.org/details/lf2007-11-21.a

It should create a video for each of the audio tracks, for example on this link there are 16 tracks. Each of the videos created should have as the background image the background image from the page with the track listing, so for our example URL the background image is at https://ia800801.us.archive.org/14/items/lf2007-11-21.a/Romp2007-11-21.flac16/img.jpg?cnt=0 

Each of these archive.org links lead to a page that contains metadata. So, for the example link above, the metadata looks like this:

" Lane Family Live at [Romp] Fox Hollow Restaurant Petersburg, NY on 2007-11-21
by Lane Family

Publication date
    2007-11-21 ( check for other copies) 
Topics
    Live concert
Collection
    LaneFamily 
Band/Artist
    Lane Family 
Item Size
    304.4M 

Romp
Fox Hollow Restaurant
Petersburg, NY
11/21/2007

Recorded: AUD > PCM
Transfer: WAV > Audacity > FLAC16
Recorded by: Christopher Lane
Transfer: Taperwayne

01. East Tennessee Blues > 48 Dogs
02. Deep Elem Blues
03. Hot Corn Cold Corn
04. Down Yonder
05. Jolly Farmer
06. Pay d'haut
07. Old Habits
08. Payday Blues
09. Blue Ridge Mountain Blues
10. Tennessee Waltz
11. Boppin' The Blues
12. Smoke That Cigarette
13. Buy A T-Shirt
14. Cover Of The Rolling Stone
15. Rolly Poly
16. Blue Eyed Sally

Addeddate
    2023-01-10 18:44:41 
Identifier
    lf2007-11-21.a 
Lineage
    Transfer: WAV > Audacity > FLAC16 
Location
    Petersburg, NY 
Scanner
    Internet Archive HTML5 Uploader 1.7.0 
Source
    Recorded: AUD > PCM 
Taped by
    Christopher Lane 
Transferred by
    Taperwayne 
Type
    sound 
Venue
    [Romp] Fox Hollow Restaurant Petersburg, NY 
Year
    2007 

"

Use this information to label the tracks with their correct names.

All of this information should be used to create the descriptionof the youtube videos. So, for example, for track 2 on this example, the description would read like "Deep Ellum Blues, performed by Romp at Fox Hollow Restaurant Petersburg, NY. Taped by Christopher Lane, Transferred by Taperwayne." and so on, with all the relevant information. Also in the description should also be a link back to the original URL that we input at the start. 

After all 16 tracks have been uploaded, we should create a youtube playlist of the 16 tracks and include the entire description text from the archive.org page in the description of the playlist.

Create a README.md, and additional MD files describing the architecture and plan for the app. Build the app itself until it is functional, using what resources seem appropriate, such as any existing API for youtube or archive.org, etc. Document how the application works with clear concise inline comments or docstrings. Keep the README.md concise and clear, with a basic section that gives an overview of the app's purpose and usage, and a technical section that describes how it works and how it is built.
