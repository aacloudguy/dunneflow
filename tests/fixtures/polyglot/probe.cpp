// C++'s half of the probe tree: a way in, a boundary, a loop and a branch.

#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

namespace probe {

constexpr int Retries = 3;

struct Setting
{
    std::string key;
    std::string value;
};

/** Read a config file, one line at a time. */
std::vector<Setting> LoadConfig(const std::string& path)
{
    std::vector<Setting> out;
    FILE* handle = fopen(path.c_str(), "r");
    if (handle == nullptr)
    {
        return out;
    }

    char line[512];
    while (fgets(line, sizeof(line), handle) != nullptr)
    {
        std::string text(line);
        const size_t split = text.find('=');
        if (split == std::string::npos)
        {
            continue;
        }
        out.push_back(Setting{text.substr(0, split), text.substr(split + 1)});
    }

    fclose(handle);
    return out;
}

}  // namespace probe

int main(int argc, char** argv)
{
    const char* root = getenv("PROBE_ROOT");
    const std::vector<probe::Setting> settings =
        probe::LoadConfig(std::string(root != nullptr ? root : ".") + "/probe.cfg");
    printf("%zu settings\n", settings.size());
    return 0;
}
