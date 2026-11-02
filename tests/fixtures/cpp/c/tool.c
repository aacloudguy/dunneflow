/* The C and C++ reader's fixture: C, which this reader reads now and the one before it
 * did not. */
#include <stdio.h>
#include <stdlib.h>

static int count_lines(const char *path)
{
    FILE *f = fopen(path, "r");
    int n = 0;
    int c;
    if (!f)
        return -1;
    while ((c = fgetc(f)) != EOF) {
        if (c == '\n')
            n++;
    }
    fclose(f);
    return n;
}

int main(int argc, char **argv)
{
    const char *path = argc > 1 ? argv[1] : getenv("TOOL_FILE");
    printf("%d lines\n", count_lines(path));
    return 0;
}
