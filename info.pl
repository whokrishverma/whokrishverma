ascii generation works differently on real face images and flat illustrations/comic

so there are v1 v2 v3 different versions for illustrations. 
    v2 is close to accurate
    v3 is way more accurate the best version achieved so far. but the only issue is that it taking only a small part of the image and not the entire image.

there is only v1 for real face images. 
    v1 is accurate but the only issue is that it doesnt track the background. 


what to do next?
    - add contribution heatmap
    - add other features as avi vashisht
    - enhance the layout like tabs and clean readible
    - add badges and achievements on github
    - understand github and maxx the profile
    - enhance the ascii versions, make the algo close to perfect.
    - try another approach of instead making an automation code. get ascii generation for the image manually and just get it the animation
    - get a folder structure in pearl file

=============================================================================================================================
FOLDER STRUCTURE

    whokrishverma/
        ├── .github/                                  -> for github to view
        │   └── workflows/
        │       └── ascii.yml
        ├── ascii.svg                                 -> converted ascii svg
        ├── info.pl                                   -> all info about the project
        ├── make_ascii_svg_illustration_v1.py         ->
        ├── make_ascii_svg_illustration_v2.py         ->
        ├── make_ascii_svg_illustration_v3.py         ->
        ├── make_ascii_svg_v1.py                      ->
        ├── photo.jpg                                 ->
        ├── photo1.jpg                                ->
        ├── photo3.jpg                                ->
        └── README.md                                 -> this will be displayed on the profile

=============================================================================================================================
HOW ITS WORKING

    main file thats running is - v3 for illustration and v1 for real image


=============================================================================================================================

the ascii bot checks the image every hour directly from github profile if changed or everytime i change the image manually in code, it also pushes the new ascii svg created. 
similarly, the heatmap bot does that every night or when there is some code pushed by me manually.