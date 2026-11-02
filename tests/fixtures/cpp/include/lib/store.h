// The C and C++ reader's fixture: a header a source file reaches only through an include
// directory the reader has to infer (`lib/store.h` is under `include/`, and nothing says so).
#pragma once

#include <string>

#define UFUNCTION(...)

namespace lib {

/** Where settings are kept. */
class Store {
public:
    virtual ~Store() = default;

    UFUNCTION(BlueprintCallable, Category = "Store")
    void Fire(int Times);

    virtual std::string Load(const std::string& key) = 0;

    int Count() const { return count_; }

private:
    int count_ = 0;
};

class FileStore final : public Store {
public:
    std::string Load(const std::string& key) override;
};

}  // namespace lib
