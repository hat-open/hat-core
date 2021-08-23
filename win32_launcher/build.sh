#!/bin/sh

set -e

CC=${CC:-x86_64-w64-mingw32-gcc}
WINDRES=${WINDRES:-x86_64-w64-mingw32-windres}

ROOT_PATH="$(cd $(dirname -- "$0"); pwd)"
BUILD_PATH="$ROOT_PATH/build"

NAME=win32_launcher
ICON=
ADMIN=
while getopts n:i:a flag; do
    case $flag in
        n)  NAME="$OPTARG";;
        i)  ICON="$OPTARG";;
        a)  ADMIN=1;;
        ?)  ;;
    esac
done
shift $(($OPTIND - 1))
CMD="$*"

if [ -z "$CMD" ]; then
    printf "Usage: %s: [-n name] [-i icon] [-a] cmd\n" $0
    exit 1
fi

rm -rf $BUILD_PATH
mkdir -p $BUILD_PATH

cat > $BUILD_PATH/main.rc << EOF
#include "winuser.h"
STRINGTABLE { 1 "dummy" }
EOF

if [ ! -z "$ICON" ]; then
ICON="$(cd $(dirname $ICON); pwd)/$(basename $ICON)"
echo "iconId ICON \"$ICON\"" >> $BUILD_PATH/main.rc
fi

if [ ! -z "$ADMIN" ]; then
MANIFEST="$BUILD_PATH/$NAME.exe.manifest"
echo "1 RT_MANIFEST \"$MANIFEST\"" >> $BUILD_PATH/main.rc
cat > $MANIFEST << EOF
<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1"
          manifestVersion="1.0">
  <trustInfo xmlns="urn:schemas-microsoft-com:asm.v2">
    <security>
      <requestedPrivileges>
        <requestedExecutionLevel
          level="requireAdministrator"
          uiAccess="false"/>
      </requestedPrivileges>
    </security>
  </trustInfo>
</assembly>
EOF
fi

$WINDRES $BUILD_PATH/main.rc $BUILD_PATH/main.rc.o
$CC -O2 -mwindows \
    -o "$BUILD_PATH/$NAME.exe" \
    -DLAUNCHER_CMD="\"$CMD\"" \
    $BUILD_PATH/main.rc.o main.c
