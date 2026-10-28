#pragma once
#include <chrono>
#include <iomanip>
#include <iostream>
using ReproClock = std::chrono::steady_clock;
inline double seconds(ReproClock::time_point start, ReproClock::time_point end) {
    return std::chrono::duration<double>(end - start).count();
}
inline void metrics(double load, double setup, double compute, std::size_t vertices) {
    std::cout << std::setprecision(17) << "REPRO_METRICS {\"load_wall_s\":" << load
              << ",\"setup_wall_s\":" << setup << ",\"compute_wall_s\":" << compute
              << ",\"total_before_export_wall_s\":" << load + setup + compute
              << ",\"vertices\":" << vertices << "}" << std::endl;
}
