// The C and C++ reader's fixture: one of each shape the reader has a rule for.
#include <cstdlib>
#include <fstream>
#include <string>
#include <vector>

#include "lib/store.h"

namespace lib {

void Store::Fire(int Times)
{
    count_ += Times;
}

std::string FileStore::Load(const std::string& key)
{
    std::ifstream in(key);
    std::string line;
    std::getline(in, line);
    return line;
}

}  // namespace lib

static int classify(int n)
{
    if (n < 0) {
        return -1;
    } else if (n == 0) {
        return 0;
    } else {
        return 1;
    }
}

int run(lib::Store& store, const std::vector<std::string>& keys)
{
    int total = 0;
    for (const auto& k : keys) {
        const std::string value = store.Load(k);
        total += static_cast<int>(value.size());
    }
    switch (classify(total)) {
        case -1:
            return 1;
        default:
            break;
    }
    try {
        store.Fire(total);
    } catch (...) {
        return 2;
    }
    return 0;
}

int main()
{
    const char* home = std::getenv("HOME");
    lib::FileStore store;
    std::vector<std::string> keys{home ? home : "/tmp"};
    return run(store, keys);
}
