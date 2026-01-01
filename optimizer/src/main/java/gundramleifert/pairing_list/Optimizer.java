package gundramleifert.pairing_list;

import com.fasterxml.jackson.databind.deser.DataFormatReaders;
import gundramleifert.pairing_list.configs.*;
import gundramleifert.pairing_list.cost_calculators.CostCalculatorBoatSchedule;
import gundramleifert.pairing_list.cost_calculators.CostCalculatorMatchMatrix;
import gundramleifert.pairing_list.cost_calculators.ICostCalculator;
import gundramleifert.pairing_list.types.BoatMatrix;
import gundramleifert.pairing_list.types.Flight;
import gundramleifert.pairing_list.types.Schedule;
import lombok.SneakyThrows;
import org.apache.commons.cli.*;

import java.io.File;
import java.util.*;
import java.util.function.Consumer;
import java.util.stream.Collectors;

import static gundramleifert.pairing_list.cost_calculators.CostCalculatorBoatSchedule.getInterFlightStat;

public class Optimizer {
  private ScheduleConfig properties;
  private OptimizationConfig optProps;
  private Random random;

  public void init(ScheduleConfig properties, OptimizationConfig optimizationConfig, Random random) {
    this.properties = properties;
    this.optProps = optimizationConfig;
    this.random = random;

  }

  private static void printQuality(ICostCalculator scorer, List<Schedule> schedules) {
    System.out.format("Score:%6.3f Age:%3d best ( %6.3f worst)\n",
            scorer.score(schedules.get(0)),
            schedules.get(0).getAge(),
            scorer.score(schedules.get(schedules.size() - 1)));
  }

//    private static void printQuality(String prefix, CostCalculatorMatchMatrix scorer, Flight schedule) {
//        System.out.format("Score:%6.3f Age:%3d %s\n", scorer.score(schedule), schedule.getAge(), prefix);
//    }

  private static void printQuality(String prefix, ICostCalculator scorer, Schedule schedule) {
    System.out.format("Score:%6.3f Age:%3d %s\n", scorer.score(schedule), schedule.getAge(), prefix);
  }

  private List<Schedule> getBestFlights(Schedule base, Random random, Consumer<Schedule> saver) {
    List<Schedule> schedules = new ArrayList<>();
    for (int i = 0; i < optProps.optMatchMatrix.individuals; i++) {
      schedules.add(new Schedule(base, Util.getRandomFlight(properties, random)));
    }
    int counter = 0;
    final CostCalculatorMatchMatrix scorer = new CostCalculatorMatchMatrix(properties, optProps.optMatchMatrix);
    OptMatchMatrixConfig optMatchMatrix = optProps.optMatchMatrix;

    for (int i = 0; i < optMatchMatrix.loops; i++) {
      for (int j = 0; j < optMatchMatrix.swapTeams; j++) {
        Schedule mutation = schedules.get(random.nextInt(schedules.size())).copy();
        MutationUtil.swapBetweenRaces(mutation, random);
        if (!schedules.contains(mutation)) {
          schedules.add(mutation);
        }
      }
      schedules.sort(Comparator.comparingDouble(scorer::scoreWithCache));
      if (schedules.size() > optMatchMatrix.individuals) {
                   /* for (Schedule schedule : schedules.subList(individuals, schedules.size())) {
                        hashes.remove(Integer.valueOf(schedule.hashCode()));
                    }*/
        schedules = new ArrayList<>(schedules.subList(0, optMatchMatrix.individuals));
      }
      if (i == optMatchMatrix.loops - 1 || (optMatchMatrix.showEveryN > 0 && counter % optMatchMatrix.showEveryN == 0)) {
//                System.out.println("------------  " + i + "  -----------------------");
//                //System.out.println("best1:" + scorer1.score(schedules.get(0)));
//                printQuality(scorer, schedules);
        //Util.printMatchMatrix(properties, schedules.get(0));
//                Util.printCount(properties, copy);
//            }
        for (Schedule s : schedules) {
          s.getOlder();
        }
        counter++;
        if (optMatchMatrix.earlyStopping > 0 && schedules.get(0).getAge() >= optMatchMatrix.earlyStopping) {
          System.out.println("Early Stopping applied");
          break;
        }
        if (saver != null && optMatchMatrix.saveEveryN > 0 && counter % optMatchMatrix.saveEveryN == 0) {
          Util.printCount(schedules.get(0).getMatchMatrix().getMatchDistribution(), false);
          saver.accept(schedules.get(0));
        }

      }
    }
//        return schedules;
    double currentValue = scorer.scoreWithCache(schedules.get(0));
    List<Schedule> collect = schedules
            .stream()
            .filter(flight -> Math.abs(scorer.scoreWithCache(flight) - currentValue) < 1e-5)
            .collect(Collectors.toList());
    System.out.println(String.format("found %d schedules with equal costs = %.3f", collect.size(), currentValue));
    return collect;
  }

  private List<Schedule> getBestFlight4Boats(Schedule best, Random random, Consumer<Schedule> saver) {
    List<Schedule> schedules = new ArrayList<>();
    OptBoatConfig optBoatUsage = optProps.optBoatUsage;
    for (int i = 0; i < optBoatUsage.individuals; i++) {
      Schedule copy = best.copy();
      Util.shuffleTeams(best.get(best.size() - 1), random);
      schedules.add(copy);
    }
    int counter = 0;
    final CostCalculatorBoatSchedule scorer = new CostCalculatorBoatSchedule(properties, optBoatUsage);
    for (int i = 0; i < optBoatUsage.loops; i++) {
      for (int j = 0; j < optBoatUsage.swapBoats; j++) {
        Schedule mutation = schedules.get(random.nextInt(schedules.size())).copy();
        MutationUtil.swapBoats(mutation, random);
        if (!schedules.contains(mutation)) {
          schedules.add(mutation);
        }
      }
      for (int j = 0; j < optBoatUsage.swapRaces; j++) {
        Schedule mutation = schedules.get(random.nextInt(schedules.size())).copy();
        MutationUtil.swapRaces(mutation, random);
        if (!schedules.contains(mutation)) {
          schedules.add(mutation);
        }
      }
      schedules.sort(Comparator.comparingDouble(scorer::scoreWithCache));
      if (schedules.size() > optBoatUsage.individuals) {
                   /* for (Schedule schedule : schedules.subList(individuals, schedules.size())) {
                        hashes.remove(Integer.valueOf(schedule.hashCode()));
                    }*/
        schedules = new ArrayList<>(schedules.subList(0, optBoatUsage.individuals));
      }
      if (i == optBoatUsage.loops - 1 || (optBoatUsage.showEveryN > 0 && counter % optBoatUsage.showEveryN == 0)) {
//                System.out.println("------------  " + i + "  -----------------------");
//                //System.out.println("best1:" + scorer1.score(schedules.get(0)));
//                printQuality(scorer, schedules);
        //Util.printMatchMatrix(properties, schedules.get(0));
//                Schedule copy = schedule.copy();
//                copy.add(schedules.get(0));
//                Util.printCount(properties, copy);
//            }
        for (Schedule s : schedules) {
          s.getOlder();
        }
        counter++;
        if (optBoatUsage.earlyStopping > 0 && schedules.get(0).getAge() >= optBoatUsage.earlyStopping) {
          System.out.println("Early Stopping applied");
          break;
        }
        if (saver != null && optBoatUsage.saveEveryN > 0 && counter % optBoatUsage.saveEveryN == 0) {
          saver.accept(schedules.get(0));
        }

      }
    }
//        return schedules;
    double currentValue = scorer.scoreWithCache(schedules.get(0));
    List<Schedule> collect = schedules
            .stream()
            .filter(flight -> Math.abs(scorer.scoreWithCache(flight) - currentValue) < 1e-5)
            .collect(Collectors.toList());
    System.out.println(String.format("found %d schedules with equal costs = %.3f", collect.size(), currentValue));
    return collect;
  }

  public Schedule optimizeMatchMatrix(Consumer<Schedule> saver) {

    Set<Schedule> schedulesBest = new LinkedHashSet<>();
    Flight flight0 = Util.getRandomFlight(properties, random);
    Schedule startSchedule = new Schedule(properties);
    startSchedule.add(flight0);
    schedulesBest.add(startSchedule);
    for (int f = 1; f < this.properties.flights; f++) {
      System.out.println(String.format("###### Flight %d ######", f + 1));
      Set<Schedule> nextSchedules = new LinkedHashSet<>();
      for (Schedule schedule : schedulesBest) {
        List<Schedule> bestFlights = getBestFlights(schedule, random, saver);
        nextSchedules.addAll(bestFlights);
      }
      CostCalculatorMatchMatrix cc = new CostCalculatorMatchMatrix(properties, optProps.optMatchMatrix);
      Schedule min = nextSchedules
              .stream()
              .min(Comparator.comparingDouble(cc::scoreWithCache))
              .orElseThrow(() -> new RuntimeException("empty schedules"));
      double costMin = cc.score(min);
      schedulesBest = nextSchedules
              .stream()
              .filter(schedule -> Math.abs(cc.score(schedule) - costMin) < 1e-5)
              .collect(Collectors.toSet());
      System.out.println(String.format("found %d best schedules for flight %d", schedulesBest.size(), f + 1));
      if (schedulesBest.size() > optProps.optMatchMatrix.maxBranches) {
        List<Schedule> collect = new ArrayList<>(schedulesBest);
        Collections.shuffle(collect, random);
        schedulesBest = new LinkedHashSet<>(collect.subList(0, optProps.optMatchMatrix.maxBranches));
      }
      System.out.println("Schedule after MatchOpt:");
      Schedule scheduleAfterMatchOpt = schedulesBest.stream().findFirst().orElseThrow(() -> new RuntimeException("empty list"));
      Util.printCount(scheduleAfterMatchOpt.getMatchMatrix().getMatchDistribution(), false);

    }
    return schedulesBest.stream().findFirst().orElseThrow(() -> new RuntimeException("empty list"));
  }

  public Schedule optimizeBoatMatrix(List<Schedule> schedulesBase, Consumer<Schedule> saver) {

    Set<Schedule> schedulesBest = new LinkedHashSet<>(schedulesBase);
    for (int f = 1; f < this.properties.flights; f++) {
      System.out.println(String.format("Flight %d:", f + 1));
      Set<Schedule> nextSchedules = new LinkedHashSet<>();
//            for (Schedule schedule : schedulesBest) {
////                List<Flight> bestFlights = getBestFlight4Boats(schedule, f, random, saver);
////                for (int j = 0; j < bestFlights.size(); j++) {
////                    Schedule scheduleNew = schedule.copy();
////                    scheduleNew.add(bestFlights.get(j));
////                    nextSchedules.add(scheduleNew);
////                }
//            }
      CostCalculatorMatchMatrix cc = new CostCalculatorMatchMatrix();
      Schedule min = nextSchedules
              .stream()
              .min(Comparator.comparingDouble(cc::scoreWithCache))
              .orElseThrow(() -> new RuntimeException("empty schedules"));
      double costMin = cc.score(min);
      schedulesBest = nextSchedules
              .stream()
              .filter(schedule -> Math.abs(cc.scoreWithCache(schedule) - costMin) < 1e-5)
              .collect(Collectors.toSet());
      System.out.println(String.format("found %d best schedules for flight %d", schedulesBest.size(), f + 1));
      if (schedulesBest.size() > optProps.optMatchMatrix.maxBranches) {
        List<Schedule> collect = new ArrayList<>(schedulesBest);
        Collections.shuffle(collect, random);
        schedulesBest = new LinkedHashSet<>(collect.subList(0, optProps.optMatchMatrix.maxBranches));
      }
      System.out.println("best so far:");
      int ii = 0;
      for (Schedule s : schedulesBest) {
        int[] matchDistribution = s.getMatchMatrix().getMatchDistribution();
        Util.printCount(matchDistribution, false);
      }
    }
    return schedulesBest.stream().findFirst().orElseThrow(() -> new RuntimeException("empty list"));
  }

  public Schedule optimizeBoatSchedule(Schedule schedule, Consumer<Schedule> saver) {
    List<Schedule> schedules = new ArrayList<>();
    OptBoatConfig optBoatUsage = optProps.optBoatUsage;
    for (int i = 0; i < optBoatUsage.individuals; i++) {
      Schedule copy = schedule.deepCopy();
      Util.shuffleBoats(copy, random);
      schedules.add(copy);
    }
    int counter = 0;
    System.out.println(String.format("run with %s", optBoatUsage));
    for (Schedule s : schedules) {
      s.resetAge();
    }
    final CostCalculatorBoatSchedule scorer = new CostCalculatorBoatSchedule(properties, optBoatUsage);
    for (int i = 0; i < optBoatUsage.loops; i++) {
      for (int j = 0; j < optBoatUsage.swapBoats; j++) {
        Schedule mutation = schedules.get(random.nextInt(schedules.size()));
        mutation = MutationUtil.swapBoatsDeepCopy(mutation, random);
        if (!schedules.contains(mutation)) {
          schedules.add(mutation);
        }
      }
      for (int j = 0; j < optBoatUsage.swapRaces; j++) {
        Schedule mutation = schedules.get(random.nextInt(schedules.size()));
        mutation = MutationUtil.swapRacesDeepCopy(mutation, random);
        if (!schedules.contains(mutation)) {
          schedules.add(mutation);
        }
      }
      schedules.sort(Comparator.comparingDouble(scorer::scoreWithCache));
      if (schedules.size() > optBoatUsage.individuals) {
                   /* for (Schedule schedule : schedules.subList(individuals, schedules.size())) {
                        hashes.remove(Integer.valueOf(schedule.hashCode()));
                    }*/
        schedules = new ArrayList<>(schedules.subList(0, optBoatUsage.individuals));
      }
      if (i == optBoatUsage.loops - 1 || (optBoatUsage.saveEveryN > 0 && counter % optBoatUsage.saveEveryN == 0)) {
//                    System.out.println("------------  " + i + "  -----------------------");
//                    //System.out.println("best1:" + scorer1.score(schedules.get(0)));
//                    printQuality("best", scorer, schedules.get(0));
////                    printQuality("middle", scorer, schedules.get(schedules.size() / 2));
//                    printQuality("worst", scorer, schedules.get(schedules.size() - 1));
        //System.out.println(saveFuel.score(properties, schedules.get(0)));
        //Util.printMatchMatrix(properties, schedules.get(0));
        BoatMatrix matchMatrix = new BoatMatrix(properties);
        Schedule scheduleBest = schedules.get(0);
        for (int flightIdx = 0; flightIdx < scheduleBest.size(); flightIdx++) {
          Flight flight = scheduleBest.get(flightIdx);
          matchMatrix.add(flight);
        }
        int[] boatDistribution = matchMatrix.getBoatDistribution();
        Util.printCount(boatDistribution, false);
        int[] ii = getInterFlightStat(schedules.get(0), properties.numTeams);
        double best = scorer.score(schedules.get(0));
        double worst = scorer.score(schedules.get(schedules.size() - 1));
        System.out.println(String.format("costs = %.3f .. %.3f", best, worst));
        System.out.println(String.format("saved Shuttles: in habour: %d at sea: %d - boat changes: %d", ii[0], ii[1], ii[2]));
      }
      for (Schedule s : schedules) {
        s.getOlder();
      }
      counter++;
      if (optBoatUsage.earlyStopping > 0 && schedules.get(0).getAge() >= optBoatUsage.earlyStopping) {
        System.out.println("Early Stopping applied");
        break;
      }
      double best = scorer.score(schedules.get(0));
      double worst = scorer.score(schedules.get(schedules.size() - 1));

      if (Math.abs(best - worst) < 1e-5) {
        System.out.println("best and worst are the same - no better solution can be expected - save and break!");
        if (saver != null) {
          System.out.println("save!");
          saver.accept(schedules.get(0));
        }
        break;
      }
      if (saver != null && optBoatUsage.saveEveryN > 0 && counter % optBoatUsage.saveEveryN == 0) {
        saver.accept(schedules.get(0));
      }
    }
    return schedules.get(0);

  }

  public static void main(String[] args) throws Exception {
    Options options = new Options();

    Option scheduleConfig = new Option(
            "s",
            "schedule_config",
            true,
            "the path to the yaml-file containing the schedule configuration");
    scheduleConfig.setRequired(false);
    options.addOption(scheduleConfig);

    Option optimizationConfig = new Option(
            "oc",
            "opt",
            true,
            "the path to the yaml-file containing the schedule configuration. If not given, take default configuration");
    optimizationConfig.setRequired(false);
    options.addOption(optimizationConfig);

    Option displayConfig = new Option(
            "dc",
            "display",
            true,
            "the path to the yaml-file containing the display configuration for the pdf");
    displayConfig.setRequired(false);
    options.addOption(displayConfig);

    Option outPdf = new Option(
            "plp",
            "pairing_list_pdf",
            true,
            "if given, save the pdf to the given path");
    displayConfig.setRequired(false);
    options.addOption(outPdf);


    Option input = new Option(
            "pli",
            "pairing_list_in",
            true,
            "if given, start with this configuration (must fit to schedule configuration), otherwise use random.");
    input.setRequired(false);
    options.addOption(input);

    Option outYml = new Option(
            "plo",
            "pairing_list_out",
            true,
            "if given, save best schedule to this file as yaml-structure");
    outYml.setRequired(false);
    options.addOption(outYml);
    Option outCsv = new Option(
            "plc",
            "pairing_list_csv",
            true,
            "if given, save best schedule to this file as csv-structure");
    outCsv.setRequired(false);
    options.addOption(outCsv);

    CommandLineParser parser = new DefaultParser();
    HelpFormatter formatter = new HelpFormatter();
    CommandLine cmd = null;

    try {
      cmd = parser.parse(options, args);
    } catch (ParseException e) {
      System.out.println(e.getMessage());
      formatter.printHelp("Method to calculate a Pairing List for the Liga-Format", options);
      System.exit(1);
    }

    String scheduleConfigValue = cmd.getOptionValue(scheduleConfig, "schedule_cfg.yml");
    ScheduleConfig scheduleProps = ScheduleConfig.readYaml(scheduleConfigValue);

    String optimizationConfigValue = cmd.getOptionValue(optimizationConfig, "opt_cfg.yml");
    OptimizationConfig optimizationProps = OptimizationConfig.readYaml(optimizationConfigValue);

    String displayConfigValue = cmd.getOptionValue(displayConfig, "display_cfg.yml");
    String outputValue = cmd.getOptionValue(outYml, "pairing_list.yml");
    String outPdfValue = cmd.getOptionValue(outPdf, "pairing_list.pdf");
    String outCsvValue = cmd.getOptionValue(outPdf, "pairing_list.csv");
    String inputValue = cmd.getOptionValue(input, null);
    if (inputValue != null && optimizationProps.optBoatUsage.loops + optimizationProps.optMatchMatrix.loops > 0) {
      throw new RuntimeException("loaded schedule but optimizations are activated");
    }
    Schedule schedule = null;
    if (inputValue != null) {
      schedule = Schedule.readYaml(new File(inputValue), null);
      System.out.println("shuffle teams");
      List<String> teams = Arrays.asList(scheduleProps.teams);
      Collections.shuffle(teams, new Random(optimizationProps.seed));
      scheduleProps.teams = teams.toArray(new String[0]);
    }
    DisplayConfig displayProps = DisplayConfig.readYaml(displayConfigValue);
    Random random = new Random(optimizationProps.seed);
    Saver saver = new Saver(outPdfValue,outputValue,outCsvValue, displayProps,scheduleProps);
//        schedule = inputValue == null ?
//                Util.getRandomSchedule(scheduleProps, random) :
//                Schedule.readYaml(new File(inputValue), scheduleProps);
    if (schedule == null) {
      Optimizer optimizer = new Optimizer();
      optimizer.init(scheduleProps, optimizationProps, random);
      schedule = optimizer.optimizeMatchMatrix(saver);
      if (optimizationProps.optBoatUsage.loops > 0) {
        schedule = Util.shuffleBoats(schedule, random);
      }
      schedule = optimizer.optimizeBoatSchedule(schedule, saver);
    }
    saver.accept(schedule);
  }
}
