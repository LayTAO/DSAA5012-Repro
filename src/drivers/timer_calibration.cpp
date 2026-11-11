#include "supplement_timer.h"
#include <fstream>
int main(){try{
 auto& t=supplement::timer();t.print();
 for(int repeat=1;repeat<=3;repeat++){
  constexpr int n=100000;volatile std::uint64_t sink=0;
  double a=supplement::wall();for(int i=0;i<n;i++){asm volatile("" ::: "memory");sink+=i;}double empty=supplement::wall()-a;
  a=supplement::wall();for(int i=0;i<n;i++){auto q=std::chrono::high_resolution_clock::now();sink+=q.time_since_epoch().count()&1;}double chrono=supplement::wall()-a;
  a=supplement::wall();for(int i=0;i<n;i++){auto q=supplement::stamp();sink+=q.t&1;}double stamp=supplement::wall()-a;
  for(int work:{1,10,100,1000}){
   auto x=supplement::stamp();double start=supplement::wall();for(int j=0;j<10000;j++)for(int k=0;k<work;k++)sink=sink*1664525+1013904223;double wall=supplement::wall()-start;auto y=supplement::stamp();
   std::cout<<"CAL_WORK {\"repeat\":"<<repeat<<",\"work\":"<<work<<",\"tsc_s\":"<<double(y.t-x.t)/t.hz<<",\"wall_s\":"<<wall<<"}\n";
  }
  std::cout<<"CAL_CALL {\"repeat\":"<<repeat<<",\"n\":"<<n<<",\"empty_s\":"<<empty<<",\"chrono_s\":"<<chrono<<",\"stamp_s\":"<<stamp<<",\"sink\":"<<sink<<"}\n";
 }
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}}
