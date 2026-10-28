#include "Hypergraph.h"
#include "Algorithm/NbrCD.h"
#include "metrics.h"
#include <fstream>
#include <stdexcept>
#include <string>

int main(int argc, char** argv) {
    try {
        if (argc != 4) throw std::runtime_error("Usage: sigmod INPUT ALGORITHM CORE_CSV_OR_DASH");
        using AlgorithmFn = void (*)(Hypergraph&);
        const AlgorithmFn algorithms[] = {
            nbrCoreDecomposition, nbrCoreDecomposition_onlyChanged,
            nbrCoreDecomposition_onlyLowerBound, nbrCoreDecomposition_no_filter,
            baseNbrCoreDecomposition_withNbrs, fullNbrCoreDecomposition,
            nbrCoreDecomposition_withNbrs
        };
        const std::string algorithm_arg(argv[2]);
        std::size_t parsed = 0;
        const int algorithm = std::stoi(algorithm_arg, &parsed);
        if (parsed != algorithm_arg.size() || algorithm < 0 || algorithm > 6)
            throw std::runtime_error("Algorithm must be 0..6");
        const auto start = ReproClock::now();
        Hypergraph graph;
        graph.loadFromFiles(argv[1]);
        std::size_t actual_vertices = 0;
        for (std::size_t vertex = 1; vertex < graph.getGraphNodeSize(); ++vertex) {
            const auto offsets = graph.getEdges(vertex);
            if (offsets.second > offsets.first) ++actual_vertices;
        }
        const auto loaded = ReproClock::now();
        algorithms[algorithm](graph);
        const auto computed = ReproClock::now();
        metrics(seconds(start, loaded), 0.0, seconds(loaded, computed), actual_vertices);
        if (std::string(argv[3]) != "-") {
            std::ofstream output(argv[3]);
            output.exceptions(std::ios::failbit | std::ios::badbit);
            output << "vertex,core\n";
            for (std::size_t vertex = 1; vertex < graph.getGraphNodeSize(); ++vertex) {
                const auto offsets = graph.getEdges(vertex);
                if (offsets.second > offsets.first)
                    output << vertex << ',' << graph.nodes_core.at(vertex) << '\n';
            }
        }
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 2;
    }
}
