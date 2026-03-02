---
name: cpp-coding-in-this-codebase
description: Use when writing or reviewing C++ or Protobuf code in this Bazel codebase and you need the repository-specific style, naming, logging, performance, and unit-testing conventions.
---

# C++ Coding in This Codebase

## Overview
这份 skill 把两类规范合并成一个可搜索的入口：
- 公司内部总结的 **C++/内存/Protobuf 常见坑与最佳实践**
- 需要用什么其他的 **skills** 帮助开发

目标很简单：写出可维护、可测、性能可控的 C++17 代码，并且别用“特殊情况”去堆条件分支。

## When to Use
- 你在这个仓库里写/改 C++（含 Proto 相关生成代码的使用方式）
- 你在做 code review，需要检查风格、一致性、性能、UT 习惯
- 你遇到性能/内存/序列化开销，想快速排查常见陷阱

## 采用的 Skills
- 必须按照 [using-superpowers](.github/skills/using-superpowers) 中的要求去查找其余的 `skills`
- 必须至少使用 [receiving-code-review](.github/skills/receiving-code-review) 和 [requesting-code-review](.github/skills/requesting-code-review) 并结合本文档的约束进行 code-review

## Non-Negotiables (Project Rules)
- **C++17**。
- 遵循 Google C++ Style Guide，并以仓库既有代码风格为准。
- **缩进超过 3 层说明结构烂了**：重构拆分，不要继续堆 if/else。
- 注释必须是 **英文**，写“原理/意图”，不要复述代码。
- **不要**用 `LOG(INFO)`（默认不打印），用 `LOG(ERROR)`。
- 避免前向声明（除非你非常确定这样做收益大且不会制造隐藏依赖）。

## Naming & API Surface
- 变量名必须表达语义，别用含糊缩写。
- **索引/循环计数一律用 `int`，禁止用 `size_t`**：
  - 本仓库大量接口/索引是 `int` 语义（global/local index、state index 等），混用 `size_t` 容易引入隐式转换、负数比较 bug、以及可读性灾难。
  - 需要用 `vector.size()` 时：用 `static_cast<int>(vec.size())`，并确保不会溢出（UT/小数据场景可接受；生产代码要先做上界检查）。
- 对“导数相关”的命名尤其严格：不要用 `grad` / `hess` / `jac` / `J` / `extr` 这类含糊缩写。
  - 用 `gradient` / `hessian` / `jacobian`
  - 用完整宾语：`wrt_imu_pose` / `wrt_extrinsic` / `wrt_lidar_pose` 等
- 字符串字面量用：
  - `constexpr char kName[] = "...";`
- 二元比较（排序/比较器）用 `lhs` / `rhs`：
  - `[](const T& lhs, const T& rhs) { ... }`
- 允许为 nullptr 的指针参数命名为 `nullable_*`。
- 输入参数传递：
  - **不可为空**：`const T&`
  - **可为空**：`const T*`（并用 `nullable_*` 命名）

## Correctness & “Good Taste”
- 优先消灭边界条件，而不是给边界条件加更多分支。
- 保持函数短小：一个函数只做一件事。

## Inheritance & Virtual Destructors
- 基类如果会被继承/多态删除，必须有 **virtual destructor**，否则 `delete Base*` 会泄漏派生类资源。
- 派生类覆盖虚函数要用 `override`。
- 类不是为继承设计：用 `final`。

## Anonymous Namespace vs `static`
- 在 `.cc` 文件里做内部链接（internal linkage），优先用匿名命名空间：
  - `namespace { ... }`
- 不要再用 `static` 去做同一件事。

## “Options struct” 习惯
- `struct Options` 之类的配置结构体 **不要加构造函数**，否则会破坏聚合初始化（花括号初始化）并降低可读性。
- 用默认成员初始化器表达默认值。

## STL / Range-for / Comparators
- 遍历 `std::map` / `std::unordered_map`：
  - 只读：`for (const auto& [key, value] : map)`
  - 避免无意义拷贝。
- 比较器必须满足严格弱序：
  - **相等必须返回 false**（`a == b` 时 compare(a,b) 为 false）。
  - 浮点相关比较要考虑容差，并加 UT。

## `std::move` on `const`
- 对 `const` 对象/引用用 `std::move()` 不会触发真正的 move（因为不能移动 const）。
- 把它当成“类型转换提示”，不要自我欺骗。

## Performance & Memory (Practical)
- 少分配：循环外复用 buffer；避免每次迭代 `new`/`malloc`。
- 用高效算法；禁止用“暴力算法”赌不会超时。
- 性能/内存问题要可测：用工具定位热点（堆分析、malloc 统计），别靠猜。
- 多线程分配争用明显时，了解 allocator（jemalloc/tcmalloc）的行为差异。

## Debugging Memory Bugs
- AddressSanitizer 能抓越界/Use-After-Free 等典型错误；优先把问题抓在测试阶段。
- 内存泄漏定位要系统化：统计 → 热点定位 → 复现 → 缩小范围。

## Debugging C++ Code (CRITICAL)

**NEVER create temporary .cc files outside the project to "test" or "verify" C++ logic.**

This is FORBIDDEN because:
1. Temporary files won't compile with project's Bazel/make8 dependencies (Eigen, protobuf, etc.)
2. Wastes time on environment setup that inevitably fails
3. Bypasses the project's build system and produces misleading results

**CORRECT approach:**
```cpp
// Add a focused debug test case in existing *_test.cc:
TEST(EncoderTest, DebugAlignmentBehavior) {
  // Set up minimal data
  // Add std::cerr << for debug output
  // Verify specific behavior
}
```

Then run: `bazel run //path:test --gtest_filter="*.Debug*"`

After debugging, either:
- Delete the debug test, OR
- Convert it to a proper regression test

## Unit Testing (UT) Conventions
- 浮点比较优先：`EXPECT_DOUBLE_EQ` / `EXPECT_FLOAT_EQ`，不要滥用 `EXPECT_NEAR`。
- Eigen 类型比较、数值 Jacobian/导数测试：优先用 `common/utils/math/testing` 的工具。
- 测试数据必须满足被测对象的 `IsValid()` 或等价有效性检查。
- 在循环中，使用 `ASSERT_*` 而不是 `EXPECT_*`，在第一个失败案例发生时，就需要停下而不是“刷屏”打印

## Protobuf Performance & Correctness
- `repeated`（尤其嵌套 repeated）会带来大量分配；性能敏感路径要非常警惕。
- 能预估容量就 `Reserve()`：
  - `mutable_points()->Reserve(num_points)`
- 大量数值序列化：优先 packed repeated，必要时把多维数据展平成一维数组降低开销。
- 比较 proto：优先用 `MessageDifferencer`，不要用 `SerializeAsString()`（map 字段未排序可能导致不稳定）。

## Common Review Checklist
- API：输入是 `const T&` 还是 `const T*`？nullable 命名是否清晰？
- 结构：有没有超过 3 层缩进？能不能拆函数/抽语义？
- 性能：循环里有没有隐式拷贝/分配？map 遍历是否结构化绑定？
- 日志：有没有多余的 `LOG(INFO)` 或者 `LOG(ERROR)`？可能导致频繁刷屏的？
- UT：浮点/Eigen 比较是否用 common/utils/math/testing 下的统一工具？数据是否满足有效性约束？
- Proto：repeated 是否 `Reserve()`？比较是否用 Differencer？
