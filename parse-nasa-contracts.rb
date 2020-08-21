require 'net/http'
require 'uri'
states = Array[ ["AK", "Alaska"], 
                ["AL", "Alabama"], 
                ["AR", "Arkansas"], 
                ["AZ", "Arizona"], 
                ["CA", "California"], 
                ["CO", "Colorado"], 
                ["CT", "Connecticut"], 
                ["DC", "District of Columbia"], 
                ["DE", "Delaware"], 
                ["FL", "Florida"], 
                ["GA", "Georgia"], 
                ["HI", "Hawaii"], 
                ["IA", "Iowa"], 
                ["ID", "Idaho"], 
                ["IL", "Illinois"], 
                ["IN", "Indiana"], 
                ["KS", "Kansas"], 
                ["KY", "Kentucky"], 
                ["LA", "Louisiana"], 
                ["MA", "Massachusetts"], 
                ["MD", "Maryland"], 
                ["ME", "Maine"], 
                ["MI", "Michigan"], 
                ["MN", "Minnesota"], 
                ["MO", "Missouri"], 
                ["MS", "Mississippi"], 
                ["MT", "Montana"], 
                ["NC", "North Carolina"], 
                ["ND", "North Dakota"], 
                ["NE", "Nebraska"], 
                ["NH", "New Hampshire"], 
                ["NJ", "New Jersey"], 
                ["NM", "New Mexico"], 
                ["NV", "Nevada"], 
                ["NY", "New York"], 
                ["OH", "Ohio"], 
                ["OK", "Oklahoma"], 
                ["OR", "Oregon"], 
                ["PA", "Pennsylvania"], 
                ["PR", "Puerto Rico"], 
                ["RI", "Rhode Island"], 
                ["SC", "South Carolina"], 
                ["SD", "South Dakota"], 
                ["TN", "Tennessee"], 
                ["TX", "Texas"], 
                ["UT", "Utah"], 
                ["VA", "Virginia"], 
                ["VI", "Virgin Islands"], 
                ["VT", "Vermont"], 
                ["WA", "Washington"], 
                ["WI", "Wisconsin"], 
                ["WV", "West Virginia"], 
                ["WY", "Wyoming"] ]


# Process the values for obligated amounts
def process_amount(raw_value)
  if raw_value.include? "-"
    neg = true
  else
    neg = false
  end
  value = Integer(raw_value.gsub(/\D+/, ''))
  if neg
    value = -(value)
  end
  value
end

total_contractors = []
total_small_businesses = []
total_educational_institutions = []
total_state_universities = []
total_minority_owned = []
total_woman_owned = []
total_hbcus = []
total_value = total_small_businesses_value = total_educational_institutions_value = total_state_universities_value = total_minority_owned_value = total_woman_owned_value = total_hbcus_value = total_grants_value = 0

fy_range = (2005..2019).to_a

fy_range.each do |year|

  fy = "FY #{year.to_s[-2,2]}"
  start_date = "#{year-1}-10-01"
  end_date   = "#{year}-09-30"

  uri = URI.parse("https://prod.nais.nasa.gov/cgibin/npdv/usmap05.cgi")
  summary = []
  #[ ["AK", "Alaska"], ["AL", "Alabama"]]
  puts "============================== #{fy} =============================="
  states.each do |st, state|

    puts "Processing #{state} (#{st}) in FY #{year}...\n"

    res = Net::HTTP.post_form(uri, 
      'bus_cat' => 'ALL',
      'fy' => fy,
      'recovery' => '0',
      'v_center' => 'ALL',
      'v_database' => fy.gsub(/\s+/, ""),
      'v_code' => '53',
      'v_district' => 'ALL',
      'v_end_date' => start_date,
      'v_start_date' => end_date,
      'v_state' => state.upcase,
      'v_state2' =>st,
      'action' => 'Export to Excel')
  
  
    count = 0
    sum = 0 

  
    contractors = []
    small_businesses = []
    woman_owned = []
    minority_owned = []
    educational_institutions = []
    hbcus = []
    state_universities = []
    non_profits = []
    grants = []
    
    small_business_value = woman_owned_value = minority_owned_value = educational_institution_value = state_university_value = hbcu_value = non_profit_value = grant_value = 0

    if !res.body.include? 'Invalid Entry' then

      File.open("#{fy.gsub(' ','-')}-nasa-state-contracts-full.txt", "a") do |f|

        res.body.split(/\n/).each do |line|
          count = count + 1
          # First time through write data headers, adding a column for state
          if count == 7 && st == states[0][0]
            f.write "State\tDistrict\t#{line}\n"
          end

          # Once past the summary data begin saving each line of information to the
          # collated file.
          if count > 7

            raw = line.split("\t")

            # Grab congressional district, making sure to confirm
            # that the provided information is actually a district number
            if ["AK","WY","MT","ND","SD","VT","DE"].include?(st)
              district = "#{st}-00"
            else
              district_number = raw[3].slice(-4,2)
              if district_number.to_i == 0
                district = ""
              else
                district = "#{st}-#{district_number}"
              end
            end

            # Raw data dump
            f.write "#{st}\t#{district}\t#{line}\n"

            #Track sum of obligations
            value = process_amount(raw[8])
            sum += value
            total_value += value

            if !contractors.include?(raw[0])
              contractors << raw[0]
            end
            
            if !total_contractors.include?(raw[0])
              total_contractors << raw[0]
            end

            # Is this a research grant?
            if raw[7].include?('Grant For Research')
              grants << raw[0] if not grants.include?(raw[0])
              grant_value += value
              total_grants_value += value
            end

            # Look in multiple fields for contract recipient category
            contract_type = raw[6] + ' ' + raw[7]

            # Record various types of contract recipients, note that total recipient counts are unique per year and
            # unique for the time span provided...but not unique year-to-year. There will be duplicates in each year's
            # count due to the fact that contracts are paid out over mulitple years.

            if (contract_type.include?('Small Business') || contract_type.include?('Small Disadvantaged Business')) && !contract_type.include?('Other Than Small Business')
              small_businesses << raw[0] if not small_businesses.include?(raw[0])
              total_small_businesses << raw[0] if not total_small_businesses.include?(raw[0])
              small_business_value += value
              total_small_businesses_value += value
            end

            if (contract_type.include?('Woman Owned') || contract_type.include?('Women Owned'))
              woman_owned << raw[0] if not woman_owned.include?(raw[0])
              total_woman_owned << raw[0] if not total_woman_owned.include?(raw[0])
              woman_owned_value += value
              total_woman_owned_value += value
            end
          
            if contract_type.include?('Minority Owned')
              minority_owned << raw[0] if not minority_owned.include?(raw[0])
              total_minority_owned << raw[0] if not total_minority_owned.include?(raw[0])
              minority_owned_value += value
              total_minority_owned_value += value
            end

            if contract_type.include?('Educational')
              educational_institutions << raw[0] if not educational_institutions.include?(raw[0])
              total_educational_institutions << raw[0] if not total_educational_institutions.include?(raw[0])
              educational_institution_value += value
              total_educational_institutions_value += value
            end

            # Attempt to determine if it is a public university, accounting for poor record-keeping and categorization particular prior to FY2009
            if (contract_type.include?('Educational') && (contract_type.include?('State') || raw[0].include?("UNIVERSITY OF #{state.upcase}") || raw[0].include?("#{state.upcase} STATE") || raw[0].include?("UNIV #{state.upcase}")))
              state_universities << raw[0] if not state_universities.include?(raw[0])
              total_state_universities << raw[0] if not total_state_universities.include?(raw[0])
              state_university_value += value
              total_state_universities_value += value
            end

            if contract_type.include?('Educational') && contract_type.include?('Historically Black')
              hbcus << raw[0] if not hbcus.include?(raw[0])
              total_hbcus << raw[0] if not total_hbcus.include?(raw[0])
              hbcu_value += value
              total_hbcus_value += value
            end

            if contract_type.include?('Nonprofit Organization') && !(contract_type.include?('University') || contract_type.include?('State'))
              non_profits << raw[0] if not non_profits.include?(raw[0])
              non_profit_value += value
            end
          
          end
        end
      end

      # Prepare summary file for the fiscal year, broken out by state
      summary << [
        st, contractors.uniq.size,
        small_businesses.uniq.size, small_business_value,
        woman_owned.uniq.size, woman_owned_value,
        minority_owned.uniq.size, minority_owned_value,
        educational_institutions.uniq.size, educational_institution_value,
        state_universities.uniq.size, state_university_value,
        hbcus.uniq.size, hbcu_value,
        non_profits.uniq.size, non_profit_value,
        grants.uniq.size, grant_value,
        sum]

      puts "#{count-7} contract actions with #{sprintf("$%2.0f",sum)} in obligations."
    end

    File.open("#{fy.gsub(' ','-')}-nasa-contracts-summary.txt","w") do |f|
      f << "State\tTotal Recipients\tNet Obligations\tSmall Businesses\tSmall Business Obligations\tWoman Owned\tWoman Owned Obligations\tMinority Owned\tMinority Owned Obligations\tEducational Institutions\tEducational Institutions Obligations\tPublic Universities\tPublic University Obligations\tHBCUs\tHBCU Obligations\tNon Profits\tNon Profit Obligations\tGrant Recipient Institutions\tGrant Obligations\n"
      summary.each do |item|
        f << "#{item[0]}\t#{item[1]}\t#{sprintf("$%2.0f",item[18])}\t#{item[2]}\t#{sprintf("$%2.0f",item[3])}\t#{item[4]}\t#{sprintf("$%2.0f",item[5])}\t#{item[6]}\t#{sprintf("$%2.0f",item[7])}\t#{item[8]}\t#{sprintf("$%2.0f",item[9])}\t#{item[10]}\t#{sprintf("$%2.0f",item[11])}\t#{item[12]}\t#{sprintf("$%2.0f",item[13])}\t#{item[14]}\t#{sprintf("$%2.0f",item[15])}\t#{item[16]}\t#{sprintf("$%2.0f",item[17])}\n"
      end
    end
  end
end
#Fiscal Year summary
File.open("FY#{fy_range.first}-FY#{fy_range.last}-nasa-contracts-summary.txt","w") do |f|
  f << "Total Recipients\tNet Obligations\tSmall Businesses\tSmall Business Total Obligations\tWoman Owned\tWoman Owned Total Obligations\tMinority Owned\tMinority Owned Total Obligations\tEducational Institutions\tEducational Institutions Total Obligations\tPublic Universities\tPublic Universities Total Obligations\tHBCUs\tHBCUs Total Obligations\tGrant Obligations\n"
  f << "#{total_contractors.uniq.size}\t#{sprintf("$%2.0f",total_value)}\t#{total_small_businesses.uniq.size}\t#{sprintf("$%2.0f",total_small_businesses_value)}\t#{total_woman_owned.uniq.size}\t#{sprintf("$%2.0f",total_woman_owned_value)}\t#{total_minority_owned.uniq.size}\t#{sprintf("$%2.0f",total_minority_owned_value)}\t#{total_educational_institutions.uniq.size}\t#{sprintf("$%2.0f",total_educational_institutions_value)}\t#{total_state_universities.uniq.size}\t#{sprintf("$%2.0f",total_state_universities_value)}\t#{total_hbcus.uniq.size}\t#{sprintf("$%2.0f",total_hbcus_value)}\t#{sprintf("$%2.0f",total_grants_value)}\n"
end
puts 'Done'