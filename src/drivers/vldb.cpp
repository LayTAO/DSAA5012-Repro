#include "hypergraph.h"
#include "algorithms.h"
#include "readhg.h"
#include "metrics.h"
#include <algorithm>
#include <fstream>
#include <stdexcept>
#include <string>

int main(int argc, char** argv) {
    try {
        if (argc != 4 || std::string(argv[2]) != "OPTIV")
            throw std::runtime_error("Usage: vldb INPUT OPTIV CORE_CSV_OR_DASH");
        if (!std::ifstream(argv[1]).good()) throw std::runtime_error("Cannot open input");
        const auto start = ReproClock::now();
        Hypergraph graph;
        dataset_to_filename["repro"] = argv[1];
        getHg("repro", graph);
        graph.dataset = "repro";
        graph.initialise();
        const auto loaded = ReproClock::now();
        // Preserve the upstream constructor's graph copy and report it separately.
        Algorithm algorithm(graph);
        const auto setup = ReproClock::now();
        local_core_OPTIV(graph.dataset, graph.hyperedges, graph.init_nodes,
                         graph.node_index, algorithm, false);
        const auto computed = ReproClock::now();
        metrics(seconds(start, loaded), seconds(loaded, setup), seconds(setup, computed),
                graph.init_nodes.size());
        std::cout << std::setprecision(17) << "VLDB_CPU_PHASES {\"init_cpu_s\":"
                  << algorithm.output.at("init_time") << ",\"iteration_cpu_s\":"
                  << algorithm.exec_time << "}" << std::endl;
        if (std::string(argv[3]) != "-") {
            std::ofstream output(argv[3]);
            output.exceptions(std::ios::failbit | std::ios::badbit);
            output << "vertex,core\n";
            auto vertices = graph.init_nodes;
            std::sort(vertices.begin(), vertices.end());
            for (const auto vertex : vertices)
                output << vertex << ',' << algorithm.core.at(vertex) << '\n';
        }
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 2;
    }
}
