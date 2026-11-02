/* C's half of the probe tree, read by the C and C++ reader: a way in, a boundary, a loop
 * and a branch. No `Setting` here: the six of them are one per language that has records. */

#include <stdio.h>
#include <stdlib.h>

static int count_entries(const char *path)
{
    FILE *handle = fopen(path, "r");
    char line[512];
    int n = 0;
    if (handle == NULL) {
        return 0;
    }
    while (fgets(line, sizeof line, handle) != NULL) {
        n++;
    }
    fclose(handle);
    return n;
}

int main(void)
{
    const char *root = getenv("PROBE_ROOT");
    printf("%d entries\n", count_entries(root != NULL ? root : "probe.cfg"));
    return 0;
}
