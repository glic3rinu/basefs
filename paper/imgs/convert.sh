ls *png | while read line; do convert $line eps2:$(echo $line | sed "s/\.png$/.eps/"); done
