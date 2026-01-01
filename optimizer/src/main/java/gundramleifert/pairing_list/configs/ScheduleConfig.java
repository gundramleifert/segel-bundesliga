package gundramleifert.pairing_list.configs;


import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.ObjectMapper;
import gundramleifert.pairing_list.Optimizer;
import gundramleifert.pairing_list.Yaml;

import java.io.File;
import java.io.IOException;
import java.net.URISyntaxException;
import java.net.URL;
import java.util.List;

public class ScheduleConfig {
  public static ScheduleConfig readYaml(String string) throws IOException, URISyntaxException {
    if (new File(string).exists()) {
      return readYaml(new File(string));
    }
    URL resource = Optimizer.class.getClassLoader().getResource(string);
    if (resource == null) {
      throw new IllegalArgumentException(String.format("file `%s` not found in resources an on disc", string));
    }
    File file = new File(resource.toURI());
    return readYaml(file);

  }

  public static ScheduleConfig readYaml(final File file) throws IOException {
    ScheduleConfig scheduleConfig;
    ObjectMapper objectMapper = Yaml.dftMapper();
    scheduleConfig = objectMapper.readValue(file, ScheduleConfig.class);
    scheduleConfig.init();
    return scheduleConfig;
  }

  public static void writeYaml(final File file, ScheduleConfig scheduleConfig) throws IOException {
    Yaml.dftMapper().writeValue(file, scheduleConfig);
  }

  public void init() {
    this.numBoats = boats.length;
    this.numTeams = teams.length;
    isFull = this.getRaces() * numBoats == numTeams;
    if (!isFull) {
      //expand with no-shows
      String[] teams_new = new String[getRaces() * numBoats];
      System.arraycopy(teams, 0, teams_new, 0, teams.length);
      for (int i = teams.length; i < teams_new.length; i++) {
        teams_new[i] = "";
      }
      this.teams = teams_new;
    }
    this.bytes = toByteArray();
  }


  @JsonProperty
  public String[] titles;

  @JsonProperty
  public int flights;
  @JsonProperty
  public String[] teams;

  @JsonProperty
  public BoatConfig[] boats;

  public int numBoats;
  public int numTeams;

  public byte[] bytes;

  public boolean isFull;


  public int getRaces() {
    return ((numTeams + numBoats - 1) / numBoats);
  }

  private byte[] toByteArray() {
    byte[] res = new byte[teams.length];
    for (int i = 0; i < teams.length; i++) {
      res[i] = (byte) i;
    }
    return res;
  }


}
