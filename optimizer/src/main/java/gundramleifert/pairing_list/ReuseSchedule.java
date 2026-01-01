package gundramleifert.pairing_list;

import gundramleifert.pairing_list.configs.*;
import gundramleifert.pairing_list.cost_calculators.CostCalculatorBoatSchedule;
import gundramleifert.pairing_list.cost_calculators.CostCalculatorMatchMatrix;
import gundramleifert.pairing_list.cost_calculators.ICostCalculator;
import gundramleifert.pairing_list.types.BoatMatrix;
import gundramleifert.pairing_list.types.Flight;
import gundramleifert.pairing_list.types.Race;
import gundramleifert.pairing_list.types.Schedule;
import lombok.SneakyThrows;
import org.apache.commons.cli.*;

import java.io.File;
import java.util.*;
import java.util.function.Consumer;
import java.util.stream.Collectors;

import static gundramleifert.pairing_list.cost_calculators.CostCalculatorBoatSchedule.getInterFlightStat;

public class ReuseSchedule {

  public static void main(String[] args) throws Exception {
    Options options = new Options();

    Option scheduleConfig = new Option(
            "s",
            "schedule_config",
            true,
            "the path to the yaml-file containing the schedule configuration");
    scheduleConfig.setRequired(false);
    options.addOption(scheduleConfig);

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

    Option input = new Option(
            "pli",
            "pairing_list_in",
            true,
            "if given, start with this configuration (must fit to schedule configuration), otherwise use random.");
    options.addOption(input);

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

    String displayConfigValue = cmd.getOptionValue(displayConfig, "display_cfg.yml");
    String outPdfValue = cmd.getOptionValue(outPdf, "pairing_list.pdf");
    String outYmlValue = cmd.getOptionValue(outYml, "pairing_list.yml");
    String outCsvValue = cmd.getOptionValue(outCsv, "pairing_list.csv");
    String inputValue = cmd.getOptionValue(input, "pairing_list.yml");
    Schedule schedule = Schedule.readYaml(new File(inputValue), null);
    if (schedule.size()!=scheduleProps.flights){
      throw new RuntimeException(String.format("loaded schedule config has %d flights but loaded pairing list has %d.", scheduleProps.flights,schedule.size()));
    }
    int cntTeams = 0;
    int cntBoats=0;
    for (Race race : schedule.get(0).races) {
      cntTeams+=race.teams.length;
      cntBoats = Math.max(cntBoats,race.teams.length);
    }
    if (cntTeams!=scheduleProps.teams.length){
      throw new RuntimeException(String.format("loaded schedule config has %d teams but loaded pairing list has %d.", scheduleProps.teams.length,cntTeams));
    }
    if (cntBoats!=scheduleProps.boats.length){
      throw new RuntimeException(String.format("loaded schedule config has %d boats but loaded pairing list has %d.", scheduleProps.boats.length,cntBoats));
    }
//      List<String> teams = Arrays.asList(scheduleProps.teams);
//      Collections.shuffle(teams, new Random(optimizationProps.seed));
//      scheduleProps.teams = teams.toArray(new String[0]);
    DisplayConfig displayProps = DisplayConfig.readYaml(displayConfigValue);
    Saver saver = new Saver(outPdfValue,outYmlValue,outCsvValue, displayProps,scheduleProps);
    saver.accept(schedule);
  }
}
